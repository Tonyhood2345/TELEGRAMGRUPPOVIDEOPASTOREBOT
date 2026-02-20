import os
import json
import datetime
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = "8083806105:AAGQTsM8kmogmc4UMkMODnsT_5HK-viO7n4"
CHAT_ID = "-1003619559876"
FOLDER_ID_ROOT = "1u7VGIK8OPFcuNOBhEtTG1UHCoFlwyVhA"

def get_drive_service():
    try:
        info = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Errore credenziali: {e}")
        return None

def main():
    service = get_drive_service()
    if not service: return

    now = datetime.datetime.now()
    settimana_anno = now.strftime("%V") 
    giorno_sett_en = now.strftime("%A") # Es: Friday
    
    # Mapping giorni in Italiano (Formato: Venerdi, Lunedi...)
    giorni_it = {
        "Monday": "Lunedi", "Tuesday": "Martedi", "Wednesday": "Mercoledi",
        "Thursday": "Giovedi", "Friday": "Venerdi", "Saturday": "Sabato", "Sunday": "Domenica"
    }
    
    # Determina se è Mattina (10:30) o Sera (19:30)
    # Se l'ora è prima delle 15:00 cerca "Mattina", altrimenti "Sera"
    fascia = "Mattina" if now.hour < 15 else "Sera"
    
    giorno_it = giorni_it.get(giorno_sett_en, "Lunedi")
    nome_file_cercato = f"{giorno_it}_{fascia}" # Es: Venerdi_Sera
    
    print(f"Ricerca -> Settimana: {settimana_anno} | File: {nome_file_cercato}")

    # 1. Cerca la cartella della settimana (es. "08")
    query_folder = f"'{FOLDER_ID_ROOT}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query_folder).execute()
    folders = results.get('files', [])

    week_folder_id = None
    for f in folders:
        if settimana_anno in f['name']:
            week_folder_id = f['id']
            print(f"Cartella trovata: {f['name']}")
            break

    if not week_folder_id:
        print(f"Errore: Cartella settimana {settimana_anno} non trovata.")
        return

    # 2. Cerca il video (es. Venerdi_Sera.mp4)
    query_video = f"'{week_folder_id}' in parents and name contains '{nome_file_cercato}' and trashed = false"
    video_results = service.files().list(q=query_video).execute()
    videos = video_results.get('files', [])

    if not videos:
        print(f"Errore: Video '{nome_file_cercato}' non trovato nella cartella.")
        return

    video = videos[0]
    print(f"Video trovato: {video['name']} (ID: {video['id']})")

    # 3. Download e Invio
    request = service.files().get_media(fileId=video['id'])
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"Download: {int(status.progress() * 100)}%")
    
    fh.seek(0)
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    files = {'video': (video['name'], fh, 'video/mp4')}
    data = {'chat_id': CHAT_ID, 'caption': f"🎬 {video['name']}"}
    
    r = requests.post(url, files=files, data=data)
    if r.status_code == 200:
        print("✅ SUCCESSO: Video inviato al gruppo!")
    else:
        print(f"❌ Errore Telegram: {r.text}")

if __name__ == "__main__":
    main()
