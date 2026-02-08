import os
import json
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from config import GDRIVE_FOLDER_ID

def get_drive_service():
    try:
        # This handles both file paths and potential JSON formatting issues
        creds = service_account.Credentials.from_service_account_file(
            'credentials.json', 
            scopes=['https://www.googleapis.com/auth/drive']
        )
        return build('drive', 'v3', credentials=creds, cache_discovery=False)
    except Exception as e:
        raise Exception(f"Failed to initialize GDrive Service: {e}")

def upload_to_gdrive(path, name):
    try:
        service = get_drive_service()
        file_metadata = {'name': name, 'parents': [GDRIVE_FOLDER_ID]}
        
        # resumable=True is required for files over 10MB
        media = MediaFileUpload(
            path, 
            mimetype='application/octet-stream', 
            resumable=True
        )
        
        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploading {name}: {int(status.progress() * 100)}%")
                
        return response.get('webViewLink')
    
    except Exception as e:
        # This will send the exact error back to bot.py
        error_msg = str(e)
        if "File not found" in error_msg:
            return "Error: GDRIVE_FOLDER_ID is wrong or Service Account not invited to folder."
        if "Insufficient Permission" in error_msg:
            return "Error: Service Account must be 'Editor' in the GDrive folder."
        return f"GDrive Error: {error_msg}"
