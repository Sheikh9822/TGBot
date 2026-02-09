import os

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# GDrive OAuth Config
CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN", "")
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
INDEX_URL = os.environ.get("INDEX_URL", "").rstrip('/')

# Telegram DB Config
DUMP_ID_RAW = os.environ.get("DUMP_CHAT_ID", "0")
try:
    DUMP_CHAT_ID = int(DUMP_ID_RAW)
except ValueError:
    DUMP_CHAT_ID = DUMP_ID_RAW
