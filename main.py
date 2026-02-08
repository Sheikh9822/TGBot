import os
import asyncio
import shutil
import aria2p
from pyrogram import Client, filters
from pyrogram.types import Message
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from config import *
from drive_upload import GDrive

# --- HEALTH CHECK SERVER ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Healthy")

def run_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    server.serve_forever()

# --- BOT LOGIC ---
aria2 = aria2p.API(aria2p.Client(host="http://localhost", port=6800, secret=""))
bot = Client("torrent_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
drive = GDrive()

def get_progress_bar(pct):
    try: pct = float(pct)
    except: pct = 0
    done = int(pct / 10)
    return f"[{'■' * done}{'□' * (10 - done)}] {pct:.2f}%"

@bot.on_message(filters.command("start"))
async def start_cmd(c, m):
    await m.reply("Bot is online. Send a magnet link or .torrent file!")

@bot.on_message(filters.regex(r'^magnet:\?xt=urn:btih:.*') | filters.document)
async def handle_download(c, m: Message):
    if m.document and not m.document.file_name.endswith(".torrent"):
        return

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    status_msg = await m.reply("⏳ Processing link...")

    try:
        if m.document:
            path = await m.download(file_name=os.path.join(DOWNLOAD_DIR, m.document.file_name))
            download = aria2.add_torrent(path)
        else:
            download = aria2.add_magnet(m.text)
        gid = download.gid
    except Exception as e:
        return await status_msg.edit(f"❌ Error: {e}")

    last_text = ""
    while True:
        try:
            dl = aria2.get_download(gid)
            
            # Handle Magnet Metadata phase
            if dl.is_metadata:
                await status_msg.edit("🧲 Fetching Magnet Metadata...")
                await asyncio.sleep(3)
                continue

            # Handle task transition (Magnet -> Actual Download)
            if dl.followed_by_ids:
                gid = dl.followed_by_ids[0]
                continue

            if dl.is_complete: break
            if dl.has_failed:
                return await status_msg.edit(f"❌ Failed: {dl.error_message}")
            
            progress = get_progress_bar(dl.progress)
            text = (f"**Downloading:** `{dl.name}`\n"
                    f"{progress}\n"
                    f"🚀 Speed: {dl.download_speed_string()}\n"
                    f"⏳ ETA: {dl.eta_string()}")
            
            if text != last_text:
                await status_msg.edit(text)
                last_text = text
        except: pass
        await asyncio.sleep(5)

    await status_msg.edit("📦 Download finished. Uploading to GDrive...")
    
    try:
        dl = aria2.get_download(gid)
        full_path = os.path.join(dl.dir, dl.name)
        
        # Verify path exists (handling single file or folder)
        if not os.path.exists(full_path):
            full_path = dl.files[0].path

        drive.upload(full_path, GDRIVE_FOLDER_ID)
        await status_msg.edit(f"✅ Successfully uploaded: `{dl.name}`")
        
        # Local Cleanup
        if os.path.isdir(full_path): shutil.rmtree(full_path)
        elif os.path.exists(full_path): os.remove(full_path)
        if full_path.endswith(".zip"): os.remove(full_path) # cleanup zips

    except Exception as e:
        await status_msg.edit(f"❌ Upload Error: {e}")

if __name__ == "__main__":
    Thread(target=run_health_server, daemon=True).start()
    bot.run()
