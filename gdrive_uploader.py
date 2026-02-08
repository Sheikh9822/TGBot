import os
import logging
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from config import GDRIVE_FOLDER_ID

logger = logging.getLogger(__name__)

def upload_to_gdrive(path, name):
    try:
        if not os.path.exists('credentials.json'):
            return "Error: credentials.json missing."

        creds = service_account.Credentials.from_service_account_file(
            'credentials.json', 
            scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)

        file_metadata = {'name': name, 'parents': [GDRIVE_FOLDER_ID]}
        media = MediaFileUpload(path, resumable=True)
        
        # supportsAllDrives=True is CRITICAL for Service Accounts
        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True, 
            ignoreDefaultVisibility=True
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
                
        return response.get('webViewLink')

    except Exception as e:
        logger.error(f"GDrive Crash: {str(e)}")
        return f"Error: {str(e)}"
