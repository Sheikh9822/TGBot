import os
import json

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# GDrive Config
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
INDEX_URL = os.environ.get("INDEX_URL", "").rstrip('/')
SERVICE_ACCOUNT_JSON = os.environ.get("SERVICE_ACCOUNT_JSON")

if SERVICE_ACCOUNT_JSON:
    with open('credentials.json', 'w') as f:
        f.write(SERVICE_ACCOUNT_JSON)

# Telegram DB Config
DUMP_ID_RAW = os.environ.get("DUMP_CHAT_ID", "0")
try:
    DUMP_CHAT_ID = int(DUMP_ID_RAW)
except ValueError:
    DUMP_CHAT_ID = DUMP_ID_RAW
