import os
import json
import datetime
import requests
import pandas as pd
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# --- VARIABILI SEGRETE PRESE DA GITHUB SECRETS ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SHEET_ID = "1SYNQjLshCUe0mutORI85EOccI7BiOvjTeUS9Y16YwKQ"

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
        print("⚠️ Credenziali YouTube mancanti nei Secrets.")
        return None

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
            'tags': ['fede', 'gesù', 'vangelo', 'preghiera'],
            'categoryId': '22' 
        },
        'status': {
            'privacyStatus': 'public' # 🟢 VIDEO PUBBLICO
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
    return response['id']

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

    # 3. CERCA IL FOGLIO PER LA DESCRIZIONE
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

    # 4. SCARICA IL VIDEO FISICAMENTE
    print("📥 Scaricamento del video in corso...")
    file_path = "video_temp.mp4"
    request = service_drive.files().get_media(fileId=video['id'])
    
    with open(file_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

    # 5. CARICA PRIMA SU YOUTUBE PER AVERE IL LINK
    youtube_link = ""
    if service_youtube:
        titolo_youtube = f"Riflessione di {giorno_it} {fascia}"
        video_id = upload_to_youtube(service_youtube, file_path, titolo_youtube, caption_testo)
        if video_id:
            youtube_link = f"https://youtu.be/{video_id}"

    # 6. INVIA VIDEO + TESTO + LINK A TELEGRAM
    if TELEGRAM_TOKEN and CHAT_ID:
        print("🚀 Inviando Video e Link a Telegram...")
        
        testo_finale = caption_testo
        cta_youtube = ""
        
        if youtube_link:
            # 🔴 Messaggio personalizzato con le emoticon sotto il video
            cta_youtube = f"\n\n🔴 Se preferisci guardarlo su YouTube... clicca qui 👇\n🔗 {youtube_link}"

        # Assicuriamoci di non superare i 1024 caratteri totali per la caption di Telegram
        max_desc_len = 1024 - len(cta_youtube)
        if len(testo_finale) > max_desc_len:
            testo_finale = testo_finale[:max_desc_len-3] + "..."
            
        caption_tg = testo_finale + cta_youtube
            
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
        with open(file_path, "rb") as video_file:
            files = {'video': (video['name'], video_file, 'video/mp4')}
            data = {'chat_id': CHAT_ID, 'caption': caption_tg, 'parse_mode': 'HTML'}
            
            r = requests.post(url, files=files, data=data)
            if r.status_code == 200:
                print("🌟 SUCCESSO! Video pubblicato su Telegram con il link in fondo.")
            else:
                print(f"❌ Errore Telegram: {r.text}")

    # 7. PULIZIA
    if os.path.exists(file_path):
        os.remove(file_path)

if __name__ == "__main__":
    main()
