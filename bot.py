import os
import json
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# --- CONFIGURAZIONE FISSA PER TEST ---
TELEGRAM_TOKEN = "8083806105:AAGQTsM8kmogmc4UMkMODnsT_5HK-viO7n4"
CHAT_ID = "-1003619559876"
FILE_ID_FISSO = "12Fh5CqpFdsdu0ajQ2JBpG5mTxBi_OxeX" # Il tuo video

def get_drive_service():
    info = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def main():
    service = get_drive_service()
    print(f"Tentativo invio video fisso ID: {FILE_ID_FISSO}")

    try:
        # Download
        request = service.files().get_media(fileId=FILE_ID_FISSO)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download: {int(status.progress() * 100)}%")
        
        fh.seek(0)

        # Invio
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
        files = {'video': ('video_test.mp4', fh, 'video/mp4')}
        data = {'chat_id': CHAT_ID, 'caption': "🚀 Test Invio Fisso"}
        
        r = requests.post(url, files=files, data=data)
        if r.status_code == 200:
            print("✅ SUCCESSO! Il video è sul gruppo.")
        else:
            print(f"❌ Errore Telegram: {r.text}")
            
    except Exception as e:
        print(f"❌ Errore durante il processo: {e}")

if __name__ == "__main__":
    main()
