import os, asyncio, time, json, libtorrent as lt, humanize, PTN, warnings
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, MessageNotModified, PeerIdInvalid, RPCError
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload

# Ignore deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Handle Dump ID conversion
DUMP_ID_RAW = os.environ.get("DUMP_CHAT_ID", "0")
try:
    DUMP_CHAT_ID = int(DUMP_ID_RAW)
except ValueError:
    DUMP_CHAT_ID = DUMP_ID_RAW

GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
INDEX_URL = os.environ.get("INDEX_URL", "").rstrip('/')

# Service Account Setup
SERVICE_ACCOUNT_JSON = os.environ.get("SERVICE_ACCOUNT_JSON")
if SERVICE_ACCOUNT_JSON:
    with open('credentials.json', 'w') as f: f.write(SERVICE_ACCOUNT_JSON)

try:
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=['https://www.googleapis.com/auth/drive'])
    drive_service = build('drive', 'v3', credentials=creds)
except Exception as e:
    print(f"GDrive Auth Error: {e}")

app = Client("LeechBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
ses = lt.session({'listen_interfaces': '0.0.0.0:6881'})
ses.apply_settings({'announce_to_all_trackers': True, 'enable_dht': True})

TRACKERS = ["udp://tracker.opentrackr.org:1337/announce", "udp://open.stealth.si:80/announce", "udp://exodus.desync.com:6969/announce"]
active_tasks = {}
FILES_PER_PAGE = 8

# --- HELPERS ---

async def edit_msg(client, chat_id, message_id, text, reply_markup=None):
    try:
        await client.edit_message_text(chat_id, message_id, text, reply_markup=reply_markup)
    except MessageNotModified: pass
    except Exception as e: print(f"Edit Error: {e}")

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

async def tg_prog(current, total, client, chat_id, message_id, start_time, filename):
    if time.time() - tg_prog.last_up < 5: return
    tg_prog.last_up = time.time()
    pct = (current / total) * 100
    speed = current / (time.time() - start_time) if (time.time() - start_time) > 0 else 0
    text = f"📤 **TG Uploading:** `{filename}`\n`{pct:.1f}%` | 🚀 `{humanize.naturalsize(speed)}/s`"
    await edit_msg(client, chat_id, message_id, text)
tg_prog.last_up = 0

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
    btns.append([InlineKeyboardButton("🚀 START PROCESS", callback_data=f"start_{h_hash}")])
    btns.append([InlineKeyboardButton("❌ CANCEL", callback_data=f"ca_{h_hash}")])
    return InlineKeyboardMarkup(btns)

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text("👋 Bot is active. Send Magnet or .torrent file.\n\n**If Dump isn't working:** Forward a message from the channel to me.")

@app.on_message(filters.forwarded & filters.private)
async def handle_forward(c, m):
    if m.forward_from_chat:
        cid = m.forward_from_chat.id
        try:
            chat = await c.get_chat(cid)
            await m.reply_text(f"✅ **Resolved Chat!**\nName: {chat.title}\nID: `{cid}`")
        except Exception as e:
            await m.reply_text(f"❌ Error Resolving Chat: {e}")

@app.on_message(filters.regex(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]+") | filters.document)
async def handle_input(c, m):
    if m.document and not m.document.file_name.endswith(".torrent"): return
    msg = await m.reply_text("🧲 **Fetching Metadata...**")
    if m.document:
        path = await m.download()
        h = ses.add_torrent({'ti': lt.torrent_info(path), 'save_path': './downloads/'}); os.remove(path)
    else:
        p = lt.parse_magnet_uri(m.text); p.save_path = './downloads/'; h = ses.add_torrent(p)
    
    for t in TRACKERS: h.add_tracker({'url': t, 'tier': 0})
    while not h.status().has_metadata: await asyncio.sleep(1)
    
    info = h.get_torrent_info(); h_hash = str(h.info_hash()); storage = info.files()
    files = [{"name": storage.file_path(i).split('/')[-1], "size": storage.file_size(i), "path": storage.file_path(i)} for i in range(info.num_files())]
    active_tasks[h_hash] = {"handle": h, "selected": [], "files": files, "chat_id": m.chat.id, "msg_id": msg.id, "cancel": False}
    h.prioritize_files([0] * info.num_files())
    await edit_msg(c, m.chat.id, msg.id, f"📂 Torrent: `{info.name()}`\nSelect files:", reply_markup=gen_selection_kb(h_hash))

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
        await q.answer("Processing started...")
        asyncio.create_task(run_download_process(c, h_hash))
    elif action == "pa": task["handle"].pause(); await q.answer("Paused")
    elif action == "re": task["handle"].resume(); await q.answer("Resumed")
    elif action == "ca":
        task["cancel"] = True; ses.remove_torrent(task["handle"]); await edit_msg(c, q.message.chat.id, q.message.id, "❌ Cancelled."); active_tasks.pop(h_hash, None)

async def run_download_process(c, h_hash):
    task = active_tasks[h_hash]
    handle, info = task["handle"], task["handle"].get_torrent_info()
    storage = info.files()
    
    for idx in sorted(task["selected"]):
        if task["cancel"]: break
        handle.file_priority(idx, 4)
        f_name = storage.file_path(idx).split('/')[-1]
        f_size = storage.file_size(idx)
        
        parsed = PTN.parse(f_name)
        final_name = f"[S{parsed.get('season',0):02d}E{parsed.get('episode',0):02d}] {parsed.get('title','File')} [{parsed.get('quality','HD')}].mkv" if parsed.get('season') else f_name

        while True:
            if task["cancel"]: break
            s = handle.status()
            prog = handle.file_progress()[idx]
            if prog >= f_size: break
            pct = (prog / f_size) * 100
            eta = get_eta(f_size - prog, s.download_rate)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏸ Pause" if not s.paused else "▶️ Resume", callback_data=f"{'pa' if not s.paused else 're'}_{h_hash}"), InlineKeyboardButton("❌ Cancel", callback_data=f"ca_{h_hash}")]])
            await edit_msg(c, task["chat_id"], task["msg_id"], f"📥 **Downloading:** `{final_name}`\n`{pct:.1f}%` | 🚀 `{humanize.naturalsize(s.download_rate)}/s` | ⏳ ETA: `{eta}`", reply_markup=kb)
            await asyncio.sleep(5)

        if not task["cancel"]:
            path = os.path.join("./downloads/", storage.file_path(idx))
            
            # STEP 1: TG DUMP
            await edit_msg(c, task["chat_id"], task["msg_id"], f"📤 **Step 1/2: Dumping to TG DB...**")
            tg_link = "Not Resolved"
            try:
                tg_file = await c.send_document(
                    chat_id=DUMP_CHAT_ID,
                    document=path,
                    caption=f"✅ `{final_name}`",
                    progress=tg_prog,
                    progress_args=(c, task["chat_id"], task["msg_id"], time.time(), final_name)
                )
                tg_link = tg_file.link
            except Exception as e:
                print(f"Dump Error: {e}")
                tg_link = f"Upload failed: {e}"

            # STEP 2: GDRIVE
            await edit_msg(c, task["chat_id"], task["msg_id"], f"☁️ **Step 2/2: Uploading to GDrive...**")
            try:
                loop = asyncio.get_event_loop()
                glink = await loop.run_in_executor(None, upload_to_gdrive, path, final_name)
                out = f"✅ **Processed:** `{final_name}`\n\n🆔 **TG Link:** [View]({tg_link})\n☁️ **GDrive:** [Link]({glink})"
                if INDEX_URL: out += f"\n⚡ **Index:** [Direct Link]({INDEX_URL}/{final_name.replace(' ', '%20')})"
                await c.send_message(task["chat_id"], out, disable_web_page_preview=True)
            except Exception as e: await c.send_message(task["chat_id"], f"❌ GDrive Error: {e}")
            finally:
                if os.path.exists(path): os.remove(path)
                handle.file_priority(idx, 0)

    await c.send_message(task["chat_id"], "🏁 Task Finished."); active_tasks.pop(h_hash, None)

if __name__ == "__main__":
    async def main():
        await app.start()
        print(f"Bot Started. Testing Dump ID: {DUMP_CHAT_ID}")
        try:
            await app.get_chat(DUMP_CHAT_ID)
            print("Dump Channel Resolution: SUCCESS")
        except Exception as e:
            print(f"Dump Channel Resolution: PENDING (Reason: {e})")
        await asyncio.Event().wait()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
