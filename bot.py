import os
import json
import datetime
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# Configurazione Telegram
TELEGRAM_TOKEN = "8083806105:AAGQTsM8kmogmc4UMkMODnsT_5HK-viO7n4"
CHAT_ID = "-1002244305824" # Ricavato dal link del gruppo (ID numerico necessario)

# Configurazione Drive
FOLDER_ID = "1u7VGIK8OPFcuNOBhEtTG1UHCoFlwyVhA"

def get_drive_service():
    info = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def main():
    service = get_drive_service()
    
    now = datetime.datetime.now()
    settimana_anno = now.strftime("%U") # Numero settimana
    giorno_settimana = now.strftime("%A").upper() # Es: MONDAY
    fascia = "MATTINA" if now.hour < 15 else "POMERIGGIO"
    
    # Mapping in Italiano come da tua richiesta
    giorni_it = {
        "MONDAY": "LUNEDI", "TUESDAY": "MARTEDI", "WEDNESDAY": "MERCOLEDI",
        "THURSDAY": "GIOVEDI", "FRIDAY": "VENERDI", "SATURDAY": "SABATO", "SUNDAY": "DOMENICA"
    }
    
    nome_file_cercato = f"{giorni_it[giorno_settimana]}_{fascia}"
    print(f"Cerco video per: Settimana {settimana_anno}, File: {nome_file_cercato}")

    # 1. Cerca la cartella della settimana
    query_folder = f"'{FOLDER_ID}' in parents and name = '{settimana_anno}' and mimeType = 'application/vnd.google-apps.folder'"
    results = service.files().list(q=query_folder).execute()
    folders = results.get('files', [])

    if not folders:
        print("Cartella settimana non trovata.")
        return

    week_folder_id = folders[0]['id']

    # 2. Cerca il video nella cartella
    query_video = f"'{week_folder_id}' in parents and name contains '{nome_file_cercato}' and mimeType contains 'video'"
    video_results = service.files().list(q=query_video).execute()
    videos = video_results.get('files', [])

    if not videos:
        print(f"Nessun video trovato con nome {nome_file_cercato}")
        return

    video_id = videos[0]['id']
    video_name = videos[0]['name']

    # 3. Download e invio a Telegram
    request = service.files().get_media(fileId=video_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    
    fh.seek(0)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    files = {'video': (video_name, fh, 'video/mp4')}
    data = {'chat_id': CHAT_ID, 'caption': f"Video di {nome_file_cercato}"}
    
    r = requests.post(url, files=files, data=data)
    if r.status_code == 200:
        print("Video inviato con successo!")
    else:
        print(f"Errore Telegram: {r.text}")

if __name__ == "__main__":
    main()
