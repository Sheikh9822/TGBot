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
# Connect to the aria2c daemon started in Dockerfile
aria2 = aria2p.API(aria2p.Client(host="http://localhost", port=6800, secret=""))
bot = Client("torrent_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
drive = GDrive()

def get_progress_bar(pct):
    try:
        pct = float(pct)
    except:
        pct = 0
    done = int(pct / 10)
    return f"[{'■' * done}{'□' * (10 - done)}] {pct:.2f}%"

@bot.on_message(filters.command("start"))
async def start(c, m):
    # FIX: Pyrogram uses .reply() or .reply_text()
    await m.reply("Bot is online! Send a magnet link or .torrent file.")

@bot.on_message(filters.regex(r'^magnet:\?xt=urn:btih:.*') | filters.document)
async def handle_download(c, m: Message):
    # Check if document is a torrent
    if m.document and not m.document.file_name.endswith(".torrent"):
        return

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    status_msg = await m.reply("Processing request...")

    try:
        if m.document:
            # Download .torrent file from Telegram first
            torrent_path = await m.download(file_name=os.path.join(DOWNLOAD_DIR, m.document.file_name))
            # FIX: aria2p.add_torrent returns a single object, aria2.add returns a list
            download = aria2.add_torrent(torrent_path, options={"dir": DOWNLOAD_DIR})
        else:
            # Add magnet link
            download = aria2.add_magnet(m.text, options={"dir": DOWNLOAD_DIR})
        
        # aria2p returns a single Download object for add_torrent/add_magnet
        gid = download.gid
    except Exception as e:
        return await status_msg.edit(f"❌ Error adding torrent: {e}")

    last_text = ""
    while True:
        try:
            dl = aria2.get_download(gid)
            if dl.is_complete:
                break
            if dl.has_failed:
                return await status_msg.edit(f"❌ Download failed: {dl.error_message}")
            
            progress = get_progress_bar(dl.progress)
            text = (f"**Downloading:** `{dl.name}`\n"
                    f"{progress}\n"
                    f"🚀 Speed: {dl.download_speed_string()}\n"
                    f"⏳ ETA: {dl.eta_string()}")
            
            # Only edit if text changed to avoid flood limits
            if text != last_text:
                await status_msg.edit(text)
                last_text = text
        except Exception as e:
            print(f"Update error: {e}")
            
        await asyncio.sleep(4)

    await status_msg.edit("📦 Download complete! Uploading to Google Drive...")
    
    try:
        # Get the path of the downloaded file/folder
        dl = aria2.get_download(gid)
        file_path = dl.files[0].path
        
        # Check if it's a directory or a single file
        # aria2p provides the root path in dl.dir
        full_path = os.path.join(dl.dir, dl.name)

        # Upload to GDrive
        drive.upload(full_path, GDRIVE_FOLDER_ID)
        await status_msg.edit(f"✅ Successfully uploaded: `{dl.name}`")
        
        # Cleanup local storage
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)
            
    except Exception as e:
        await status_msg.edit(f"❌ GDrive Upload Error: {e}")

if __name__ == "__main__":
    # Start health check server for Koyeb
    Thread(target=run_health_server, daemon=True).start()
    print("Bot is starting...")
    bot.run()
