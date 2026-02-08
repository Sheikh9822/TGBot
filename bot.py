import os
import asyncio
import time
import libtorrent as lt
import humanize
import warnings
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified

# Import our modular components
import config
from utils import edit_msg, gen_selection_kb, clean_rename, get_eta, get_prog_bar
from tg_uploader import upload_to_tg_db
from gdrive_uploader import upload_to_gdrive

# Silence Libtorrent 1.2.x deprecation warnings for cleaner Koyeb logs
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Initialize Pyrogram Client
app = Client(
    "LeechBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

# Initialize Torrent Session (Legacy syntax for Libtorrent 1.2.x compatibility)
ses = lt.session()
ses.listen_on(6881, 6891)
ses.apply_settings({
    'announce_to_all_trackers': True, 
    'enable_dht': True, 
    'download_rate_limit': 0,
    'connections_limit': 200
})

# High-speed trackers to boost peer discovery
TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://9.rarbg.com:2810/announce",
    "udp://tracker.torrent.eu.org:451/announce"
]

active_tasks = {}

@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text(
        "👋 **Ultimate Torrent Leech Bot**\n\n"
        "1. Send a Magnet link or upload a .torrent file.\n"
        "2. Use the menu to select files.\n"
        "3. Bot will dump to Telegram DB and upload to GDrive."
    )

@app.on_message(filters.forwarded & filters.private)
async def handle_forward(c, m):
    """Used to resolve Private Channel IDs for the Dump setup"""
    if m.forward_from_chat:
        try:
            chat = await c.get_chat(m.forward_from_chat.id)
            await m.reply_text(f"✅ **Resolved Chat:**\nName: {chat.title}\nID: `{chat.id}`")
        except Exception as e:
            await m.reply_text(f"❌ Error: {e}")

@app.on_message(filters.regex(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]+") | filters.document)
async def handle_input(c, m):
    if m.document and not m.document.file_name.endswith(".torrent"):
        return

    msg = await m.reply_text("🧲 **Fetching Metadata...**")
    
    try:
        if m.document:
            path = await m.download()
            h = ses.add_torrent({'ti': lt.torrent_info(path), 'save_path': './downloads/'})
            os.remove(path)
        else:
            h = lt.add_magnet_uri(ses, m.text, {'save_path': './downloads/'})
        
        for t in TRACKERS:
            h.add_tracker({'url': t, 'tier': 0})
            
    except Exception as e:
        return await edit_msg(c, m.chat.id, msg.id, f"❌ **Invalid Input:** {e}")

    # Wait for metadata
    while not h.has_metadata():
        await asyncio.sleep(1)
    
    info = h.get_torrent_info()
    h_hash = str(h.info_hash())
    
    # Generate file list for selection
    files = []
    for i in range(info.num_files()):
        files.append({
            "name": info.file_at(i).path.split('/')[-1], 
            "size": info.file_at(i).size, 
            "path": info.file_at(i).path
        })
    
    active_tasks[h_hash] = {
        "handle": h, 
        "selected": [], 
        "files": files, 
        "chat_id": m.chat.id, 
        "msg_id": msg.id, 
        "cancel": False
    }
    
    # Skip all files initially to save disk until user confirms selection
    h.prioritize_files([0] * info.num_files())
    
    await edit_msg(c, m.chat.id, msg.id, f"📂 **Torrent:** `{info.name()}`\nSelect files below:", reply_markup=gen_selection_kb(active_tasks, h_hash))

@app.on_callback_query()
async def callbacks(c, q: CallbackQuery):
    data = q.data.split("_")
    action, h_hash = data[0], data[1]
    task = active_tasks.get(h_hash)
    
    if not task:
        return await q.answer("Task Expired.", show_alert=True)
    
    if action == "tog":
        idx, p = int(data[2]), int(data[3])
        if idx in task["selected"]:
            task["selected"].remove(idx)
        else:
            task["selected"].append(idx)
        # Update the markup to show the checkmark
        try:
            await q.message.edit_reply_markup(gen_selection_kb(active_tasks, h_hash, p))
        except MessageNotModified:
            pass
        
    elif action == "page":
        try:
            await q.message.edit_reply_markup(gen_selection_kb(active_tasks, h_hash, int(data[2])))
        except MessageNotModified:
            pass
        
    elif action == "start":
        if not task["selected"]:
            return await q.answer("❌ Select at least one file!", show_alert=True)
        await q.answer("🚀 Starting process...")
        asyncio.create_task(run_process(c, h_hash))
        
    elif action == "ca":
        task["cancel"] = True
        ses.remove_torrent(task["handle"])
        active_tasks.pop(h_hash, None)
        await edit_msg(c, q.message.chat.id, q.message.id, "❌ **Task Cancelled.**")

async def run_process(c, h_hash):
    task = active_tasks[h_hash]
    handle, info = task["handle"], task["handle"].get_torrent_info()
    
    for idx in sorted(task["selected"]):
        if task["cancel"]:
            break
            
        handle.file_priority(idx, 4) # 4 is normal priority
        file_info = info.file_at(idx)
        f_name = file_info.path.split('/')[-1]
        f_size = file_info.size
        final_name = clean_rename(f_name)

        # 📥 DOWNLOAD LOOP
        while True:
            if task["cancel"]:
                break
            s = handle.status()
            prog = handle.file_progress()[idx]
            
            if prog >= f_size:
                break
            
            pct = (prog / f_size) * 100
            eta = get_eta(f_size - prog, s.download_rate)
            
            text = (
                f"📥 **Downloading:** `{final_name}`\n"
                f"[{get_prog_bar(pct)}] {pct:.1f}%\n"
                f"🚀 `{humanize.naturalsize(s.download_rate)}/s` | ⏳ ETA: {eta}\n"
                f"👥 P: {s.num_peers} S: {s.num_seeds}"
            )
            await edit_msg(c, task["chat_id"], task["msg_id"], text)
            await asyncio.sleep(5)

        # 📤 UPLOAD PHASE
        if not task["cancel"]:
            path = os.path.join("./downloads/", file_info.path)
            
            # 1. Telegram Dump
            await edit_msg(c, task["chat_id"], task["msg_id"], f"📤 **Step 1/2:** Uploading to Telegram DB...")
            tg_link = await upload_to_tg_db(c, path, final_name, task["chat_id"], task["msg_id"])
            
            # 2. Google Drive Upload
            await edit_msg(c, task["chat_id"], task["msg_id"], f"☁️ **Step 2/2:** Uploading to GDrive...")
            try:
                loop = asyncio.get_event_loop()
                glink = await loop.run_in_executor(None, upload_to_gdrive, path, final_name)
                
                if glink.startswith("Error"):
                    await c.send_message(task["chat_id"], f"❌ **GDRIVE FAILED**\n`{glink}`")
                else:
                    out = (
                        f"✅ **Leech Success**\n"
                        f"📝 `{final_name}`\n\n"
                        f"🆔 [Telegram DB]({tg_link})\n"
                        f"☁️ [Google Drive]({glink})"
                    )
                    if config.INDEX_URL: 
                        clean_url = final_name.replace(' ', '%20')
                        out += f"\n⚡ [Direct Index Link]({config.INDEX_URL}/{clean_url})"
                    
                    await c.send_message(task["chat_id"], out, disable_web_page_preview=True)
            except Exception as e:
                await c.send_message(task["chat_id"], f"❌ **GDrive Fatal Error:**\n`{e}`")
            finally:
                # Immediate Disk Cleanup
                if os.path.exists(path):
                    os.remove(path)
                handle.file_priority(idx, 0)

    await c.send_message(task["chat_id"], "🏁 **All tasks finished.**")
    active_tasks.pop(h_hash, None)

if __name__ == "__main__":
    async def main():
        print("Bot starting...")
        await app.start()
        
        # Warm up Peer Cache for Dump Channel
        try:
            await app.get_chat(config.DUMP_CHAT_ID)
            print(f"Dump Channel {config.DUMP_CHAT_ID} Resolved.")
        except:
            print("Warning: Could not resolve Dump Channel at startup.")
            
        print("Bot is LIVE!")
        await asyncio.Event().wait()
    
    # Wrap in retry loop to handle FloodWait
    while True:
        try:
            asyncio.get_event_loop().run_until_complete(main())
        except FloodWait as e:
            print(f"FloodWait hit! Sleeping {e.value}s")
            time.sleep(e.value + 5)
        except Exception as e:
            print(f"Bot Crash: {e}")
            time.sleep(10)
