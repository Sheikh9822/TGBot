import os, asyncio, time, libtorrent as lt, humanize, warnings
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from pyrogram.errors import FloodWait

import config
from utils import edit_msg, gen_selection_kb, clean_rename, get_eta, get_prog_bar
from tg_uploader import upload_to_tg_db
from gdrive_uploader import upload_to_gdrive

warnings.filterwarnings("ignore", category=DeprecationWarning)

app = Client("LeechBot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)
ses = lt.session({'listen_interfaces': '0.0.0.0:6881'})
active_tasks = {}

@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text("👋 **Modular Torrent Leech Bot**\nSend Magnet or .torrent file.")

@app.on_message(filters.forwarded & filters.private)
async def handle_forward(c, m):
    if m.forward_from_chat:
        try:
            chat = await c.get_chat(m.forward_from_chat.id)
            await m.reply_text(f"✅ Resolved: {chat.title}\nID: `{chat.id}`")
        except: pass

@app.on_message(filters.regex(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]+") | filters.document)
async def handle_input(c, m):
    if m.document and not m.document.file_name.endswith(".torrent"): return
    msg = await m.reply_text("🧲 Fetching Metadata...")
    if m.document:
        path = await m.download()
        h = ses.add_torrent({'ti': lt.torrent_info(path), 'save_path': './downloads/'}); os.remove(path)
    else:
        params = lt.parse_magnet_uri(m.text); params.save_path = './downloads/'; h = ses.add_torrent(params)
    
    while not h.status().has_metadata: await asyncio.sleep(1)
    
    info = h.get_torrent_info()
    h_hash = str(h.info_hash())
    files = []
    for i in range(info.num_files()):
        files.append({"name": info.file_at(i).path.split('/')[-1], "size": info.file_at(i).size, "path": info.file_at(i).path})
    
    active_tasks[h_hash] = {"handle": h, "selected": [], "files": files, "chat_id": m.chat.id, "msg_id": msg.id, "cancel": False}
    h.prioritize_files([0] * info.num_files())
    await edit_msg(c, m.chat.id, msg.id, f"📂 Torrent: `{info.name()}`", reply_markup=gen_selection_kb(active_tasks, h_hash))

@app.on_callback_query()
async def callbacks(c, q: CallbackQuery):
    data = q.data.split("_")
    action, h_hash = data[0], data[1]
    task = active_tasks.get(h_hash)
    if not task: return
    
    if action == "tog":
        idx, p = int(data[2]), int(data[3])
        if idx in task["selected"]: task["selected"].remove(idx)
        else: task["selected"].append(idx)
        await q.message.edit_reply_markup(gen_selection_kb(active_tasks, h_hash, p))
    elif action == "page":
        await q.message.edit_reply_markup(gen_selection_kb(active_tasks, h_hash, int(data[2])))
    elif action == "start":
        await q.answer("Processing started...")
        asyncio.create_task(run_process(c, h_hash))
    elif action == "ca":
        task["cancel"] = True; active_tasks.pop(h_hash, None)
        await edit_msg(c, q.message.chat.id, q.message.id, "❌ Cancelled.")

async def run_process(c, h_hash):
    task = active_tasks[h_hash]
    handle, info = task["handle"], task["handle"].get_torrent_info()
    
    for idx in sorted(task["selected"]):
        if task["cancel"]: break
        handle.file_priority(idx, 4)
        file_info = info.file_at(idx)
        f_name = file_info.path.split('/')[-1]
        f_size = file_info.size
        final_name = clean_rename(f_name)

        while True:
            if task["cancel"]: break
            s = handle.status()
            prog = handle.file_progress()[idx]
            if prog >= f_size: break
            
            pct = (prog / f_size) * 100
            eta = get_eta(f_size - prog, s.download_rate)
            text = (f"📥 Downloading: `{final_name}`\n"
                    f"[{get_prog_bar(pct)}] {pct:.1f}%\n"
                    f"🚀 `{humanize.naturalsize(s.download_rate)}/s` | ⏳ ETA: {eta}")
            await edit_msg(c, task["chat_id"], task["msg_id"], text)
            await asyncio.sleep(5)

        if not task["cancel"]:
            path = os.path.join("./downloads/", file_info.path)
            
            # 1. TG Uploader
            await edit_msg(c, task["chat_id"], task["msg_id"], f"📤 Step 1/2: Uploading to TG DB...")
            tg_link = await upload_to_tg_db(c, path, final_name, task["chat_id"], task["msg_id"])
            
            # 2. GDrive Uploader
            await edit_msg(c, task["chat_id"], task["msg_id"], f"☁️ Step 2/2: Uploading to GDrive...")
            try:
                loop = asyncio.get_event_loop()
                glink = await loop.run_in_executor(None, upload_to_gdrive, path, final_name)
                
                out = f"✅ `{final_name}`\n\n🆔 [Telegram DB]({tg_link})\n☁️ [GDrive]({glink})"
                if config.INDEX_URL: 
                    clean_url = final_name.replace(' ', '%20')
                    out += f"\n⚡ [Direct Index Link]({config.INDEX_URL}/{clean_url})"
                await c.send_message(task["chat_id"], out, disable_web_page_preview=True)
            except Exception as e: await c.send_message(task["chat_id"], f"GDrive Error: {e}")
            finally:
                if os.path.exists(path): os.remove(path)
                handle.file_priority(idx, 0)

    await c.send_message(task["chat_id"], "🏁 Task Finished.")
    active_tasks.pop(h_hash, None)

if __name__ == "__main__":
    async def run_bot():
        await app.start()
        try: await app.get_chat(config.DUMP_CHAT_ID)
        except: pass
        print("Bot is Live!")
        await asyncio.Event().wait()
    
    asyncio.get_event_loop().run_until_complete(run_bot())
