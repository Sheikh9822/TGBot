import os
import time
import asyncio
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, GDRIVE_FOLDER_ID
from utils import edit_msg, get_prog_bar

def upload_to_gdrive(path, filename, client, chat_id, message_id):
    try:
        creds = Credentials(
            None, 
            refresh_token=REFRESH_TOKEN, 
            token_uri="https://oauth2.googleapis.com/token", 
            client_id=CLIENT_ID, 
            client_secret=CLIENT_SECRET
        )
        service = build('drive', 'v3', credentials=creds, static_discovery=False)
        
        file_metadata = {'name': filename, 'parents': [GDRIVE_FOLDER_ID]}
        media = MediaFileUpload(path, resumable=True)
        request = service.files().create(body=file_metadata, media_body=media, fields='id')
        
        response = None
        last_up = 0
        loop = asyncio.get_event_loop()

        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = status.progress() * 100
                if time.time() - last_up > 5:
                    text = f"☁️ **GDrive Uploading:** `{filename}`\n{get_prog_bar(pct)} {pct:.1f}%"
                    asyncio.run_coroutine_threadsafe(edit_msg(client, chat_id, message_id, text), loop)
                    last_up = time.time()

        file_id = response.get('id')
        return f"https://drive.google.com/open?id={file_id}"
    except Exception as e:
        return f"GDrive Error: {e}"
