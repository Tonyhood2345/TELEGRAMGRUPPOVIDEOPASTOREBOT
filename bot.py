import os
import json
import datetime
import requests
import pandas as pd
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials # <-- NUOVO IMPORTO PER YOUTUBE
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload # <-- NUOVO IMPORTO

# --- VARIABILI SEGRETE PRESE DA GITHUB SECRETS ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SHEET_ID = "1SYNQjLshCUe0mutORI85EOccI7BiOvjTeUS9Y16YwKQ"

# --- NUOVI SECRETS PER YOUTUBE ---
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")

def get_drive_service():
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        print("❌ ERRORE: Variabile GOOGLE_APPLICATION_CREDENTIALS mancante.")
        return None
        
    info = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def get_youtube_service():
    if not all([YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN]):
        print("⚠️ Credenziali YouTube mancanti nei Secrets. Salto l'upload su YouTube.")
        return None

    # Creiamo le credenziali usando il Refresh Token
    creds = Credentials(
        None,
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        refresh_token=YT_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token"
    )
    return build('youtube', 'v3', credentials=creds)

def pulisci_testo(testo):
    if pd.isna(testo): return ""
    return str(testo).strip().lower().replace(" ", "").replace("_", "").replace("ì", "i").replace("è", "e")

def upload_to_youtube(youtube, file_path, title, description):
    print("🚀 Inizio caricamento su YouTube...")
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['bot', 'automazione', 'fede'],
            'categoryId': '22' # Categoria: Persone e Blog
        },
        'status': {
            'privacyStatus': 'private' # ⚠️ IMPOSTATO SU PRIVATO PER TEST. Cambia in 'public' quando sei pronto.
        }
    }
    
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype='video/mp4')
    request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Caricamento YouTube al {int(status.progress() * 100)}%")
            
    print(f"✅ Video caricato su YouTube! ID: {response['id']}")
    print(f"🔗 Link: https://youtu.be/{response['id']}")

def main():
    service_drive = get_drive_service()
    service_youtube = get_youtube_service()
    if not service_drive: return

    now = datetime.datetime.now()
    
    settimana_sheet = str(int(now.strftime("%V"))) 
    settimana_folder = now.strftime("%V")
    
    giorno_sett_en = now.strftime("%A")
    giorni_it = {"Monday": "Lunedì", "Tuesday": "Martedì", "Wednesday": "Mercoledì", "Thursday": "Giovedì", "Friday": "Venerdì", "Saturday": "Sabato", "Sunday": "Domenica"}
    
    fascia = "Mattina" if now.hour < 15 else "Pomeriggio"
    giorno_it = giorni_it.get(giorno_sett_en, "Lunedì")
    nome_video_cercato = f"{giorno_it.replace('ì','i')}_{fascia}"

    # 1. CERCA LA CARTELLA
    query_folder = f"mimeType = 'application/vnd.google-apps.folder' and name contains '{settimana_folder}' and trashed = false"
    folders = service_drive.files().list(q=query_folder).execute().get('files', [])
    if not folders: 
        print(f"❌ ERRORE: Nessuna cartella trovata per '{settimana_folder}'.")
        return
    
    # 2. CERCA IL VIDEO
    query_video = f"'{folders[0]['id']}' in parents and name contains '{nome_video_cercato}' and trashed = false"
    videos = service_drive.files().list(q=query_video).execute().get('files', [])
    if not videos: 
        print(f"❌ ERRORE: Nessun video trovato con '{nome_video_cercato}'.")
        return
    
    video = videos[0]
    print(f"✅ Video trovato su Drive: {video['name']}")

    # 3. CERCA IL FOGLIO
    caption_testo = f"🎬 Ecco il video di {giorno_it} {fascia}!\n\nSia Gloria a Dio!" 
    try:
        csv_export_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        df = pd.read_csv(csv_export_url, dtype=str) 
        
        mask_sett = df.iloc[:, 0].str.strip() == settimana_sheet
        mask_giorno = df.iloc[:, 2].apply(pulisci_testo) == pulisci_testo(giorno_it)
        mask_fase = df.iloc[:, 3].apply(pulisci_testo) == pulisci_testo(fascia)
        
        riga = df[mask_sett & mask_giorno & mask_fase]
        
        if not riga.empty:
            descrizione = str(riga.iloc[0, 5]).strip() 
            if descrizione and descrizione.lower() != "nan":
                caption_testo = descrizione
    except Exception as e:
        print(f"⚠️ Errore lettura Foglio Google: {e}")

    # 4. SCARICA IL VIDEO FISICAMENTE (Necessario per YouTube)
    print("📥 Scaricamento del video in corso...")
    file_path = "video_temp.mp4"
    request = service_drive.files().get_media(fileId=video['id'])
    
    with open(file_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

    # 5. INVIA A TELEGRAM
    if TELEGRAM_TOKEN and CHAT_ID:
        print("🚀 Inviando a Telegram...")
        # Adattiamo la caption per i limiti di Telegram
        caption_tg = caption_testo if len(caption_testo) <= 1024 else caption_testo[:1000] + "...\n#amen"
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
        with open(file_path, "rb") as video_file:
            r = requests.post(url, files={'video': video_file}, data={'chat_id': CHAT_ID, 'caption': caption_tg})
            if r.status_code == 200:
                print("🌟 SUCCESSO! Video pubblicato su Telegram.")
            else:
                print(f"❌ Errore Telegram: {r.text}")

    # 6. CARICA SU YOUTUBE
    if service_youtube:
        # Usa il nome del file (senza .mp4) come titolo del video, oppure usa una stringa fissa
        titolo_youtube = f"Video di {giorno_it} {fascia}"
        upload_to_youtube(service_youtube, file_path, titolo_youtube, caption_testo)

    # 7. PULIZIA
    if os.path.exists(file_path):
        os.remove(file_path)

if __name__ == "__main__":
    main()
