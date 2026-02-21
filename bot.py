import os
import json
import datetime
import requests
import pandas as pd
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
    giorno_sett_en = now.strftime("%A")
    
    giorni_it = {
        "Monday": "Lunedi", "Tuesday": "Martedi", "Wednesday": "Mercoledi",
        "Thursday": "Giovedi", "Friday": "Venerdi", "Saturday": "Sabato", "Sunday": "Domenica"
    }
    
    fascia = "Mattina" if now.hour < 15 else "Sera"
    giorno_it = giorni_it.get(giorno_sett_en, "Lunedi")
    nome_file_cercato = f"{giorno_it}_{fascia}"
    
    print(f"Ricerca -> Settimana: {settimana_anno} | File: {nome_file_cercato}")

    # 1. CERCA LA CARTELLA DELLA SETTIMANA
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

    # 2. CERCA IL VIDEO
    query_video = f"'{week_folder_id}' in parents and name contains '{nome_file_cercato}' and trashed = false"
    video_results = service.files().list(q=query_video).execute()
    videos = video_results.get('files', [])

    if not videos:
        print(f"Errore: Video '{nome_file_cercato}' non trovato nella cartella.")
        return

    video = videos[0]
    print(f"Video trovato: {video['name']} (ID: {video['id']})")

    # 3. CERCA E LEGGI IL PIANO EDITORIALE (EXCEL)
    query_excel = f"'{week_folder_id}' in parents and name contains 'Piano_Editoriale' and trashed = false"
    excel_results = service.files().list(q=query_excel).execute()
    excels = excel_results.get('files', [])

    # Didascalia di base in caso di emergenza
    caption_telegram = f"🎬 Ecco il video di {giorno_it} {fascia}!\n\nSia Gloria a Dio!" 

    if excels:
        excel_file = excels[0]
        print(f"File Excel trovato: {excel_file['name']}")
        
        req_excel = service.files().get_media(fileId=excel_file['id'])
        fh_excel = io.BytesIO()
        dl_excel = MediaIoBaseDownload(fh_excel, req_excel)
        done_excel = False
        while not done_excel:
            _, done_excel = dl_excel.next_chunk()
        fh_excel.seek(0)
        
        try:
            df = pd.read_excel(fh_excel)
            # Cerca la riga dove la colonna 'Nome File' è uguale al nome del video trovato
            riga = df[df['Nome File'] == video['name']]
            
            if not riga.empty:
                descrizione = str(riga.iloc[0]['Descrizione'])
                hashtag = str(riga.iloc[0]['Hashtag'])
                
                # Assembla la didascalia finale
                caption_telegram = f"{descrizione}\n\n{hashtag}"
                
                # Telegram supporta max 1024 caratteri per le didascalie media. Taglio di sicurezza.
                if len(caption_telegram) > 1024:
                    caption_telegram = caption_telegram[:1000] + "...\n#amen"
                
                print("✅ Didascalia estratta perfettamente dall'Excel!")
            else:
                print("⚠️ Video non trovato nell'Excel, uso didascalia base.")
        except Exception as e:
            print(f"⚠️ Errore nella lettura dell'Excel: {e}")
    else:
        print("⚠️ Nessun file Excel trovato. Uso didascalia base.")

    # 4. DOWNLOAD VIDEO E INVIO A TELEGRAM
    request = service.files().get_media(fileId=video['id'])
    fh_video = io.BytesIO()
    downloader = MediaIoBaseDownload(fh_video, request)
    done_video = False
    while not done_video:
        status, done_video = downloader.next_chunk()
        if status:
            print(f"Download Video: {int(status.progress() * 100)}%")
    
    fh_video.seek(0)
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    files = {'video': (video['name'], fh_video, 'video/mp4')}
    data = {'chat_id': CHAT_ID, 'caption': caption_telegram}
    
    print("Inviando il pacchetto a Telegram...")
    r = requests.post(url, files=files, data=data)
    if r.status_code == 200:
        print("✅ SUCCESSO: Video e Didascalia inviati al gruppo!")
    else:
        print(f"❌ Errore Telegram: {r.text}")

if __name__ == "__main__":
    main()
