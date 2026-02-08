import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import GDRIVE_CREDS

class GDrive:
    def __init__(self):
        if not GDRIVE_CREDS:
            raise Exception("GDRIVE_CREDENTIALS_JSON is not set!")
        creds = service_account.Credentials.from_service_account_info(
            GDRIVE_CREDS, scopes=['https://www.googleapis.com/auth/drive'])
        self.service = build('drive', 'v3', credentials=creds)

    def upload(self, file_path, parent_id="root"):
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [parent_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        request = self.service.files().create(body=file_metadata, media_body=media, fields='id')
        
        response = None
        while response is None:
            status, response = request.next_chunk()
        return response.get('id')
