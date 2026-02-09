import os
import base64

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
INDEX_URL = os.environ.get("INDEX_URL", "").rstrip('/')
DUMP_CHAT_ID = int(os.environ.get("DUMP_CHAT_ID", 0))

# OAuth Token Handling
GDRIVE_TOKEN_BASE64 = os.environ.get("GDRIVE_TOKEN_BASE64", "")

if GDRIVE_TOKEN_BASE64:
    with open('token.pickle', 'wb') as f:
        f.write(base64.b64decode(GDRIVE_TOKEN_BASE64))
