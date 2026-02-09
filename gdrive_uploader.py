import os
import pickle
import logging
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
from config import GDRIVE_FOLDER_ID

logger = logging.getLogger(__name__)

def get_drive_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("GDrive Token Expired or Invalid. Re-generate token.pickle.")

    return build('drive', 'v3', credentials=creds, cache_discovery=False)

def upload_to_gdrive(path, name):
    try:
        service = get_drive_service()
        file_metadata = {'name': name, 'parents': [GDRIVE_FOLDER_ID]}
        media = MediaFileUpload(path, mimetype='application/octet-stream', resumable=True)
        
        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
        
        return response.get('webViewLink')

    except Exception as e:
        logger.error(f"GDrive Crash: {str(e)}")
        return f"Error: {str(e)}"
