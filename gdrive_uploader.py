import os, time, asyncio, logging
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
import config, utils

def upload_to_gdrive(path, name, client, chat_id, msg_id, loop):
    try:
        creds = Credentials(
            token=None, refresh_token=config.REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=config.CLIENT_ID, client_secret=config.CLIENT_SECRET,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        creds.refresh(Request())
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        media = MediaFileUpload(path, mimetype='application/octet-stream', resumable=True)
        request = service.files().create(
            body={'name': name, 'parents': [config.GDRIVE_FOLDER_ID]},
            media_body=media, fields='id, webViewLink', supportsAllDrives=True
        )
        response, last_up = None, 0
        while response is None:
            status, response = request.next_chunk()
            if status and time.time() - last_up > 5:
                pct = int(status.progress() * 100)
                text = f"☁️ **Step 2/2: GDrive Uploading**\n📝 `{name}`\n{utils.get_prog_bar(pct)} `{pct}%`"
                asyncio.run_coroutine_threadsafe(utils.edit_msg(client, chat_id, msg_id, text), loop)
                last_up = time.time()
        return response.get('webViewLink')
    except Exception as e: return f"Error: {e}"
