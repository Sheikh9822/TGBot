import os
import logging
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from config import GDRIVE_FOLDER_ID

# Setup logging to see errors in Koyeb Console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upload_to_gdrive(path, name):
    try:
        # 1. Check if credentials file exists
        if not os.path.exists('credentials.json'):
            return "Error: credentials.json file missing on server."

        # 2. Initialize Service
        creds = service_account.Credentials.from_service_account_file(
            'credentials.json', 
            scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)

        # 3. Setup Metadata
        file_metadata = {'name': name, 'parents': [GDRIVE_FOLDER_ID]}
        media = MediaFileUpload(path, resumable=True)
        
        logger.info(f"Starting GDrive upload for: {name}")

        # 4. Perform Upload
        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Upload Progress: {int(status.progress() * 100)}%")
                
        return response.get('webViewLink')

    except Exception as e:
        logger.error(f"GDrive Crash: {str(e)}")
        return f"Error: {str(e)}"
