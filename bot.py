import os
import asyncio
import time
import libtorrent as lt
import humanize
import warnings
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from pyrogram.errors import FloodWait

# Import our modular components
import config
from utils import edit_msg, gen_selection_kb, clean_rename, get_eta, get_prog_bar
from tg_uploader import upload_to_tg_db
from gdrive_uploader import upload_to_gdrive

# Ignore DeprecationWarnings from Libtorrent 1.2.x on Koyeb
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Initialize Pyrogram Client
app = Client(
    "LeechBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

# Initialize Torrent Session
ses = lt.session({'listen_interfaces': '0.0.0.0:6881'})
ses.apply_settings({
    'announce_to_all_trackers': True, 
    'enable_dht': True, 
    'download_rate_limit': 0,
    'connections_limit': 200
})

# High-performance trackers
TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://9.rarbg.com:2810/announce"
]

active_tasks = {}

@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text(
        "👋 **Modular Torrent Leech Bot**\n\n"
        "1. Send a Magnet link or .torrent file.\n"
        "2. Select the files you want.\n"
        "3. Bot will upload to TG DB and GDrive sequentially."
    )

@app.on_message(filters.forwarded & filters.private)
async def handle_forward(c, m):
    """Handles forwarded messages to resolve Private Channel IDs"""
    if m.forward_from_chat:
        try:
            chat = await c.get_chat(m.forward_from_chat.id)
            await m.reply_text(f"✅ **Resolved Chat Info:**\nName: {chat.title}\nID: `{chat.id}`")
        except Exception as e:
            await m.reply_text(f"❌ Error resolving chat: {e}")

@app.on_message(filters.regex(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]+") | filters.document)
async def handle_input(c, m):
    # Filter for .torrent files if document
    if m.document and not m.document.file_name.endswith(".torrent"):
        return

    msg = await m.reply_text("🧲 **Fetching Metadata...**")
    
    try:
        if m.document:
            path = await m.download()
            h = ses.add_torrent({'ti': lt.torrent_info(path), 'save_path': './downloads/'})
            os.remove(path)
        else:
            params = lt.parse_magnet_uri(m.text)
            params.save_path = './downloads/'
            h = ses.add_torrent(params)
        
        for t in TRACKERS:
            h.add_tracker({'url': t, 'tier': 0})
            
    except Exception as e:
        return await msg.edit(f"❌ **Invalid Input:** {e}")

    # Wait for metadata
    while not h.status().has_metadata:
        await asyncio.sleep(1)
    
    info = h.get_torrent_info()
    h_hash = str(h.info_hash())
    
    # Store file data for selection menu
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
    
    # Don't download anything until user selects
    h.prioritize_files([0] * info.num_files())
    
    await edit_msg(c, m.chat.id, msg.id, f"📂 **Torrent:** `{info.name()}`\nSelect files below:", reply_markup=gen_selection_kb(active_tasks, h_hash))

@app.on_callback_query()
async def callbacks(c, q: CallbackQuery):
    data = q.data.split("_")
    action, h_hash = data[0], data[1]
    task = active_tasks.get(h_hash)
    
    if not task:
        return await q.answer("Task Expired or Bot Restarted.", show_alert=True)
    
    if action == "tog":
        idx, p = int(data[2]), int(data[3])
        if idx in task["selected"]:
            task["selected"].remove(idx)
        else:
            task["selected"].append(idx)
        await q.message.edit_reply_markup(gen_selection_kb(active_tasks, h_hash, p))
        
    elif action == "page":
        await q.message.edit_reply_markup(gen_selection_kb(active_tasks, h_hash, int(data[2])))
        
    elif action == "start":
        if not task["selected"]:
            return await q.answer("❌ Select at least one file!", show_alert=True)
        await q.answer("🚀 Starting Process...")
        asyncio.create_task(run_process(c, h_hash))
        
    elif action == "ca":
        task["cancel"] = True
        ses.remove_torrent(task["handle"])
        active_tasks.pop(h_hash, None)
        await edit_msg(c, q.message.chat.id, q.message.id, "❌ **Task Cancelled and Deleted.**")

async def run_process(c, h_hash):
    task = active_tasks[h_hash]
    handle = task["handle"]
    info = handle.get_torrent_info()
    
    for idx in sorted(task["selected"]):
        if task["cancel"]:
            break
            
        handle.file_priority(idx, 4) # Set priority to Normal
        file_info = info.file_at(idx)
        f_name = file_info.path.split('/')[-1]
        f_size = file_info.size
        final_name = clean_rename(f_name)

        # DOWNLOAD LOOP
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

        # UPLOAD PHASE
        if not task["cancel"]:
            path = os.path.join("./downloads/", file_info.path)
            
            # 1. Telegram DB Upload
            await edit_msg(c, task["chat_id"], task["msg_id"], f"📤 **Step 1/2:** Uploading to Telegram DB...")
            tg_link = await upload_to_tg_db(c, path, final_name, task["chat_id"], task["msg_id"])
            
            # 2. GDrive Upload
            await edit_msg(c, task["chat_id"], task["msg_id"], f"☁️ **Step 2/2:** Uploading to GDrive...")
            try:
                loop = asyncio.get_event_loop()
                # Run the blocking GDrive upload in an executor
                glink = await loop.run_in_executor(None, upload_to_gdrive, path, final_name)
                
                # Check if uploader returned an error string
                if glink.startswith("Error") or glink.startswith("GDrive Error"):
                    await c.send_message(task["chat_id"], f"❌ **GDRIVE FAILED**\n{glink}")
                else:
                    # Final success message
                    out = (
                        f"✅ **Leech Success**\n\n"
                        f"📝 `{final_name}`\n\n"
                        f"🆔 [Telegram DB Copy]({tg_link})\n"
                        f"☁️ [Google Drive Link]({glink})"
                    )
                    
                    if config.INDEX_URL:
                        clean_url_name = final_name.replace(' ', '%20')
                        out += f"\n⚡ [Direct Index Link]({config.INDEX_URL}/{clean_url_name})"
                        
                    await c.send_message(task["chat_id"], out, disable_web_page_preview=True)
                    
            except Exception as e:
                await c.send_message(task["chat_id"], f"❌ **GDrive Fatal Error:** {e}")
            finally:
                # Cleanup local disk immediately to save Koyeb space
                if os.path.exists(path):
                    os.remove(path)
                handle.file_priority(idx, 0) # Stop seeding/downloading this file

    # Task Cleanup
    await c.send_message(task["chat_id"], "🏁 **All selected files processed.**")
    active_tasks.pop(h_hash, None)

if __name__ == "__main__":
    async def run_bot():
        print("Starting Bot...")
        await app.start()
        
        # Resolve Dump Chat at startup to avoid PeerIdInvalid errors
        try:
            await app.get_chat(config.DUMP_CHAT_ID)
            print(f"Dump Channel {config.DUMP_CHAT_ID} Resolved Successfully.")
        except Exception as e:
            print(f"Warning: Could not resolve Dump Channel. Ensure ID is correct and Bot is Admin. Error: {e}")
            
        print("Bot is Live!")
        await asyncio.Event().wait()
    
    # Handle FloodWait and restarts
    while True:
        try:
            asyncio.get_event_loop().run_until_complete(run_bot())
        except FloodWait as e:
            print(f"FloodWait hit! Sleeping for {e.value} seconds...")
            time.sleep(e.value + 1)
        except Exception as e:
            print(f"Fatal Error: {e}")
            time.sleep(10)
