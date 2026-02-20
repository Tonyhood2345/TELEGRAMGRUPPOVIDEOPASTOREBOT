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
CHAT_ID = "-1003619559876"  # ID aggiornato col prefisso -100
FOLDER_ID_ROOT = "1u7VGIK8OPFcuNOBhEtTG1UHCoFlwyVhA"

def get_drive_service():
    # Legge le credenziali dal Secret di GitHub
    info = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def main():
    service = get_drive_service()
    
    # Calcolo tempo e nomi file
    now = datetime.datetime.now()
    # %V restituisce la settimana dell'anno (ISO 8601)
    settimana_anno = now.strftime("%V") 
    giorno_settimana = now.strftime("%A").upper()
    
    # 10:30 (Mattina) o 19:30 (Pomeriggio)
    fascia = "MATTINA" if now.hour < 15 else "POMERIGGIO"
    
    giorni_it = {
        "MONDAY": "LUNEDI", "TUESDAY": "MARTEDI", "WEDNESDAY": "MERCOLEDI",
        "THURSDAY": "GIOVEDI", "FRIDAY": "VENERDI", "SATURDAY": "SABATO", "SUNDAY": "DOMENICA"
    }
    
    nome_file_cercato = f"{giorni_it[giorno_settimana]}_{fascia}"
    print(f"Ricerca in corso: Settimana {settimana_anno}, Video: {nome_file_cercato}")

    # 1. Trova la cartella della settimana (es. "08")
    query_folder = f"'{FOLDER_ID_ROOT}' in parents and name = '{settimana_anno}' and mimeType = 'application/vnd.google-apps.folder'"
    results = service.files().list(q=query_folder).execute()
    folders = results.get('files', [])

    if not folders:
        print(f"ERRORE: Cartella settimana '{settimana_anno}' non trovata su Drive.")
        return

    week_folder_id = folders[0]['id']

    # 2. Cerca il video che contiene il nome (es. "LUNEDI_MATTINA")
    query_video = f"'{week_folder_id}' in parents and name contains '{nome_file_cercato}' and mimeType contains 'video'"
    video_results = service.files().list(q=query_video).execute()
    videos = video_results.get('files', [])

    if not videos:
        print(f"ERRORE: Video '{nome_file_cercato}' non trovato nella cartella {settimana_anno}.")
        return

    video_id = videos[0]['id']
    video_name = videos[0]['name']

    # 3. Download in memoria RAM
    print(f"Download di {video_name}...")
    request = service.files().get_media(fileId=video_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    
    fh.seek(0)
    
    # 4. Invio a Telegram
    print("Invio a Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    files = {'video': (video_name, fh, 'video/mp4')}
    data = {'chat_id': CHAT_ID, 'caption': f"🎬 Ecco il video di {nome_file_cercato.replace('_', ' ')}!"}
    
    r = requests.post(url, files=files, data=data)
    if r.status_code == 200:
        print("✅ Pubblicazione completata!")
    else:
        print(f"❌ Errore Telegram: {r.text}")

if __name__ == "__main__":
    main()
