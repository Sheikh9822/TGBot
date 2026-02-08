import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from config import GDRIVE_FOLDER_ID

# Initialize GDrive Service
creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=['https://www.googleapis.com/auth/drive'])
drive_service = build('drive', 'v3', credentials=creds)

def upload_to_gdrive(path, name):
    meta = {'name': name, 'parents': [GDRIVE_FOLDER_ID]}
    media = MediaFileUpload(path, resumable=True)
    request = drive_service.files().create(body=meta, media_body=media, fields='id, webViewLink')
    resp = None
    while resp is None:
        _, resp = request.next_chunk()
    return resp.get('webViewLink')
