import os, asyncio, time, json, libtorrent as lt, humanize, PTN, warnings
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, MessageNotModified, PeerIdInvalid, RPCError
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload

warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# Try to get ID as int, if fails (like a username), keep as string
DUMP_ID_RAW = os.environ.get("DUMP_CHAT_ID", "0")
try:
    DUMP_CHAT_ID = int(DUMP_ID_RAW)
except ValueError:
    DUMP_CHAT_ID = DUMP_ID_RAW

GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
INDEX_URL = os.environ.get("INDEX_URL", "").rstrip('/')

# GDrive Setup
SERVICE_ACCOUNT_JSON = os.environ.get("SERVICE_ACCOUNT_JSON")
if SERVICE_ACCOUNT_JSON:
    with open('credentials.json', 'w') as f: f.write(SERVICE_ACCOUNT_JSON)

creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=['https://www.googleapis.com/auth/drive'])
drive_service = build('drive', 'v3', credentials=creds)

app = Client("LeechBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
ses = lt.session({'listen_interfaces': '0.0.0.0:6881'})

active_tasks = {}
FILES_PER_PAGE = 8

# --- HELPERS ---
async def edit_msg(client, chat_id, message_id, text, reply_markup=None):
    try: await client.edit_message_text(chat_id, message_id, text, reply_markup=reply_markup)
    except MessageNotModified: pass
    except Exception as e: print(f"Edit Error: {e}")

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
    await edit_msg(client, chat_id, message_id, f"📤 **TG Uploading:** `{filename}`\n`{pct:.1f}%` | 🚀 `{humanize.naturalsize(speed)}/s`")
tg_prog.last_up = 0

# --- HANDLERS ---
@app.on_message(filters.command("start"))
async def start(c, m): 
    await m.reply_text("👋 Bot is active.\n\n**If Dump isn't working:**\n1. Add bot to channel as Admin.\n2. Forward any message from the channel to this bot.")

# MAGIC FIX: This handler allows the bot to "learn" the channel ID when you forward a message
@app.on_message(filters.forwarded & filters.private)
async def handle_forward(c, m):
    if m.forward_from_chat:
        cid = m.forward_from_chat.id
        try:
            chat = await c.get_chat(cid)
            await m.reply_text(f"✅ **Resolved Chat!**\nName: {chat.title}\nID: `{cid}`\n\nMake sure this ID matches your `DUMP_CHAT_ID` in Koyeb.")
        except Exception as e:
            await m.reply_text(f"❌ Error: {e}")

@app.on_message(filters.regex(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]+") | filters.document)
async def handle_input(c, m):
    if m.document and not m.document.file_name.endswith(".torrent"): return
    msg = await m.reply_text("🧲 **Fetching Metadata...**")
    if m.document:
        path = await m.download(); h = ses.add_torrent({'ti': lt.torrent_info(path), 'save_path': './downloads/'}); os.remove(path)
    else:
        p = lt.parse_magnet_uri(m.text); p.save_path = './downloads/'; h = ses.add_torrent(p)
    
    while not h.status().has_metadata: await asyncio.sleep(1)
    info = h.get_torrent_info(); h_hash = str(h.info_hash()); storage = info.files()
    files = [{"name": storage.file_path(i).split('/')[-1], "size": storage.file_size(i), "path": storage.file_path(i)} for i in range(info.num_files())]
    active_tasks[h_hash] = {"handle": h, "selected": [], "files": files, "chat_id": m.chat.id, "msg_id": msg.id, "cancel": False}
    h.prioritize_files([0] * info.num_files())
    # Corrected call to gen_selection_kb (logic omitted for space, keep your existing one)
    from bot_utils import gen_selection_kb # Assume helper or keep inline
    await edit_msg(c, m.chat.id, msg.id, f"📂 Torrent: `{info.name()}`\nSelect files:", reply_markup=gen_selection_kb(active_tasks, h_hash))

# ... (Include your callbacks and run_download_process logic here) ...

if __name__ == "__main__":
    async def main():
        await app.start()
        print(f"Bot Started. Testing Dump ID: {DUMP_CHAT_ID}")
        try:
            await app.get_chat(DUMP_CHAT_ID)
            print("Dump Channel Resolution: SUCCESS")
        except Exception as e:
            print(f"Dump Channel Resolution: PENDING (Reason: {e})")
            print("ACTION: Forward a message from the channel to the bot to fix this.")
        await asyncio.Event().wait()

    asyncio.get_event_loop().run_until_complete(main())
