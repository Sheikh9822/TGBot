import os
import json
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# GDrive settings
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "root")
GDRIVE_JSON_STR = os.environ.get("GDRIVE_CREDENTIALS_JSON", "")
GDRIVE_CREDS = json.loads(GDRIVE_JSON_STR) if GDRIVE_JSON_STR else None

# App settings
DOWNLOAD_DIR = "/tmp/downloads"
PORT = int(os.environ.get("PORT", 8080))  # For Koyeb health check
TG_LIMIT = 2000 * 1024 * 1024  # 2GB Telegram limit
