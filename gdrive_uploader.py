import os
import logging
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
import config

logger = logging.getLogger(__name__)

def get_drive_service():
    # Build credentials from individual environment variables
    creds = Credentials(
        token=None,  # Will be refreshed
        refresh_token=config.REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.CLIENT_ID,
        client_secret=config.CLIENT_SECRET,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    
    # Refresh the token to get a valid access_token
    try:
        creds.refresh(Request())
    except Exception as e:
        raise Exception(f"OAuth Refresh Failed: {e}")

    return build('drive', 'v3', credentials=creds, cache_discovery=False)

def upload_to_gdrive(path, name):
    try:
        service = get_drive_service()
        file_metadata = {'name': name, 'parents': [config.GDRIVE_FOLDER_ID]}
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
        logger.error(f"GDrive Error: {str(e)}")
        return f"Error: {str(e)}"
