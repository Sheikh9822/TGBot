import os
import logging
import time
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
import config

def get_drive_service():
    creds = Credentials(
        token=None,
        refresh_token=config.REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.CLIENT_ID,
        client_secret=config.CLIENT_SECRET,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    creds.refresh(Request())
    return build('drive', 'v3', credentials=creds, cache_discovery=False)

def upload_to_gdrive(path, name, progress_callback=None):
    try:
        service = get_drive_service()
        file_metadata = {'name': name, 'parents': [config.GDRIVE_FOLDER_ID]}
        media = MediaFileUpload(path, mimetype='application/octet-stream', resumable=True)
        
        request = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink')

        response = None
        last_update = 0
        start_time = time.time()
        
        while response is None:
            status, response = request.next_chunk()
            if status and progress_callback:
                # Update every 5 seconds to avoid TG flood
                if time.time() - last_update > 5:
                    pct = int(status.progress() * 100)
                    current = status.resumable_progress
                    total = status.total_size
                    speed = current / (time.time() - start_time)
                    progress_callback(pct, speed)
                    last_update = time.time()
        
        return response.get('webViewLink')
    except Exception as e:
        return f"Error: {str(e)}"
