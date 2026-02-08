import os, asyncio, time, json, libtorrent as lt, humanize, PTN
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
INDEX_URL = os.environ.get("INDEX_URL", "").rstrip('/')

# Service Account JSON from Env
SERVICE_ACCOUNT_JSON = os.environ.get("SERVICE_ACCOUNT_JSON")
if SERVICE_ACCOUNT_JSON:
    with open('credentials.json', 'w') as f: f.write(SERVICE_ACCOUNT_JSON)

# GDrive Setup
creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=['https://www.googleapis.com/auth/drive'])
drive_service = build('drive', 'v3', credentials=creds)

# Torrent Engine
app = Client("LeechBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
ses = lt.session()
ses.listen_on(6881, 6891)
ses.apply_settings({'announce_to_all_trackers': True, 'enable_dht': True, 'download_rate_limit': 0})

TRACKERS = ["udp://tracker.opentrackr.org:1337/announce", "udp://open.stealth.si:80/announce", "udp://exodus.desync.com:6969/announce"]

active_tasks = {}
FILES_PER_PAGE = 8

# --- UTILS ---
def get_eta(rem, speed):
    if speed <= 0: return "Unknown"
    return time.strftime("%Hh %Mm %Ss", time.gmtime(rem / speed))

def upload_to_gdrive(path, name):
    meta = {'name': name, 'parents': [GDRIVE_FOLDER_ID]}
    media = MediaFileUpload(path, resumable=True)
    request = drive_service.files().create(body=meta, media_body=media, fields='id, webViewLink')
    resp = None
    while resp is None: _, resp = request.next_chunk()
    return resp.get('webViewLink')

def gen_selection_kb(h_hash, page=0):
    task = active_tasks[h_hash]
    files, selected = task["files"], task["selected"]
    start, end = page * FILES_PER_PAGE, (page + 1) * FILES_PER_PAGE
    btns = []
    for i, f in enumerate(files[start:end]):
        idx = start + i
        icon = "✅" if idx in selected else "⬜"
        btns.append([InlineKeyboardButton(f"{icon} {f['name'][:35]}", callback_data=f"tog_{h_hash}_{idx}_{page}")])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{h_hash}_{page-1}"))
    if end < len(files): nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{h_hash}_{page+1}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("🚀 START DOWNLOAD", callback_data=f"start_{h_hash}")])
    btns.append([InlineKeyboardButton("❌ CANCEL", callback_data=f"ca_{h_hash}")])
    return InlineKeyboardMarkup(btns)

# --- HANDLERS ---
@app.on_message(filters.command("start"))
async def start(c, m): await m.reply_text("👋 Send Magnet or .torrent file to start!")

@app.on_message(filters.regex(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]+") | filters.document)
async def handle_input(c, m):
    if m.document and not m.document.file_name.endswith(".torrent"): return
    msg = await m.reply_text("🧲 **Fetching Metadata...**")
    if m.document:
        path = await m.download(); handle = lt.add_torrent(ses, {'ti': lt.torrent_info(path), 'save_path': './downloads/'}); os.remove(path)
    else:
        handle = lt.add_magnet_uri(ses, m.text, {'save_path': './downloads/'})
    for t in TRACKERS: handle.add_tracker({'url': t, 'tier': 0})
    while not handle.has_metadata(): await asyncio.sleep(1)
    
    info = handle.get_torrent_info()
    h_hash = str(handle.info_hash())
    files = [{"name": info.file_at(i).path.split('/')[-1], "size": info.file_at(i).size, "path": info.file_at(i).path} for i in range(info.num_files())]
    active_tasks[h_hash] = {"handle": handle, "selected": [], "files": files, "chat_id": m.chat.id, "msg_id": msg.id, "cancel": False}
    handle.prioritize_files([0] * info.num_files())
    await msg.edit(f"📂 Torrent: `{info.name()}`\nSelect files:", reply_markup=gen_selection_kb(h_hash))

@app.on_callback_query()
async def callbacks(c, q: CallbackQuery):
    data = q.data.split("_")
    action, h_hash = data[0], data[1]
    task = active_tasks.get(h_hash)
    if not task: return await q.answer("Task Expired.")

    if action == "tog":
        idx, p = int(data[2]), int(data[3])
        if idx in task["selected"]: task["selected"].remove(idx)
        else: task["selected"].append(idx)
        await q.message.edit_reply_markup(gen_selection_kb(h_hash, p))
    elif action == "page": await q.message.edit_reply_markup(gen_selection_kb(h_hash, int(data[2])))
    elif action == "start":
        if not task["selected"]: return await q.answer("Select at least one file!")
        await q.answer("Added to Queue")
        asyncio.create_task(run_download(c, h_hash))
    elif action == "pa": task["handle"].pause(); await q.answer("Paused")
    elif action == "re": task["handle"].resume(); await q.answer("Resumed")
    elif action == "ca":
        task["cancel"] = True; ses.remove_torrent(task["handle"]); await q.message.edit("❌ Cancelled."); active_tasks.pop(h_hash, None)

async def run_download(c, h_hash):
    task = active_tasks[h_hash]
    handle, info = task["handle"], task["handle"].get_torrent_info()
    for idx in sorted(task["selected"]):
        if task["cancel"]: break
        file = info.file_at(idx)
        handle.file_priority(idx, 4)
        
        # Auto-Rename Logic
        parsed = PTN.parse(file.path.split('/')[-1])
        final_name = f"[S{parsed.get('season',0):02d}E{parsed.get('episode',0):02d}] {parsed.get('title','File')} [{parsed.get('quality','HD')}].mkv" if parsed.get('season') else file.path.split('/')[-1]

        while True:
            if task["cancel"]: break
            s = handle.status()
            prog = handle.file_progress()[idx]
            if prog >= file.size: break
            pct = (prog / file.size) * 100
            eta = get_eta(file.size - prog, s.download_rate)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏸ Pause" if not s.paused else "▶️ Resume", callback_data=f"{'pa' if not s.paused else 're'}_{h_hash}"), InlineKeyboardButton("❌ Cancel", callback_data=f"ca_{h_hash}")]])
            try:
                await c.edit_message_text(task["chat_id"], task["msg_id"], f"📥 **Downloading:** `{final_name}`\n`{pct:.1f}%` | 🚀 `{humanize.naturalsize(s.download_rate)}/s`\n⏳ ETA: `{eta}` | 👥 P: `{s.num_peers}`", reply_markup=kb)
            except: pass
            await asyncio.sleep(5)

        if not task["cancel"]:
            await c.edit_message_text(task["chat_id"], task["msg_id"], f"☁️ **Uploading:** `{final_name}`")
            path = os.path.join("./downloads/", file.path)
            try:
                loop = asyncio.get_event_loop()
                glink = await loop.run_in_executor(None, upload_to_gdrive, path, final_name)
                out = f"✅ **Uploaded:** `{final_name}`\n🔗 [GDrive Link]({glink})"
                if INDEX_URL: out += f"\n⚡ [Direct Index Link]({INDEX_URL}/{final_name.replace(' ', '%20')})"
                await c.send_message(task["chat_id"], out, disable_web_page_preview=True)
            except Exception as e: await c.send_message(task["chat_id"], f"❌ Error: {e}")
            finally:
                if os.path.exists(path): os.remove(path)
                handle.file_priority(idx, 0)
    await c.send_message(task["chat_id"], "🏁 Task Finished."); active_tasks.pop(h_hash, None)

if __name__ == "__main__":
    while True:
        try: app.run()
        except FloodWait as e: time.sleep(e.value + 5)
        except Exception: time.sleep(10)
