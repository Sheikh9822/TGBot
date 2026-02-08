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

# 1. Health Check for Koyeb
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Healthy")

def run_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    server.serve_forever()

# 2. Torrent Downloader Init
aria2 = aria2p.API(aria2p.Client(host="http://localhost", port=6800, secret=""))
bot = Client("torrent_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
drive = GDrive()

def get_progress_bar(pct):
    pct = float(pct)
    done = int(pct / 10)
    return f"[{'■' * done}{'□' * (10 - done)}] {pct:.2f}%"

@bot.on_message(filters.command("start"))
async def start(c, m):
    await m.reply_message("Send a magnet link or .torrent file!")

@bot.on_message(filters.regex(r'^magnet:\?xt=urn:btih:.*') | filters.document)
async def handle_download(c, m: Message):
    if m.document and not m.document.file_name.endswith(".torrent"):
        return

    # Create download dir
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    link = m.text if m.text else await m.download()
    try:
        download = aria2.add(link, options={"dir": DOWNLOAD_DIR})
    except Exception as e:
        return await m.reply(f"Error: {e}")

    status_msg = await m.reply("Initializing download...")
    gid = download.gid

    while True:
        try:
            dl = aria2.get_download(gid)
            if dl.is_complete: break
            if dl.has_failed:
                return await status_msg.edit(f"Download failed: {dl.error_message}")
            
            progress = get_progress_bar(dl.progress)
            text = (f"**Downloading:** `{dl.name}`\n"
                    f"{progress}\n"
                    f"🚀 Speed: {dl.download_speed_string()}\n"
                    f"⏳ ETA: {dl.eta_string()}")
            
            await status_msg.edit(text)
        except: pass
        await asyncio.sleep(5)

    await status_msg.edit("Download complete! Preparing upload...")
    file_path = dl.files[0].path # Simplification: assumes single file torrent

    # Upload to GDrive
    try:
        drive.upload(file_path, GDRIVE_FOLDER_ID)
        await status_msg.edit("✅ Successfully uploaded to GDrive!")
    except Exception as e:
        await status_msg.edit(f"❌ GDrive Upload Error: {e}")

    # Cleanup
    if os.path.exists(file_path):
        os.remove(file_path)

if __name__ == "__main__":
    Thread(target=run_health_server, daemon=True).start()
    bot.run()
