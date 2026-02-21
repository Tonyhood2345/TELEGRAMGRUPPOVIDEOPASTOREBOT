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
    
    print(f"Ricerca Globale -> Settimana: {settimana_anno} | File: {nome_file_cercato}")

    # 1. CERCA LA CARTELLA DELLA SETTIMANA OVUNQUE (Radar Globale)
    query_folder = f"mimeType = 'application/vnd.google-apps.folder' and name contains '{settimana_anno}' and trashed = false"
    results = service.files().list(q=query_folder).execute()
    folders = results.get('files', [])

    if not folders:
        print(f"Errore: Nessuna cartella trovata con il numero '{settimana_anno}' nel nome.")
        print("Soluzione: Condividi la cartella su Drive con l'email del Service Account come Editor!")
        return

    week_folder_id = folders[0]['id']
    print(f"✅ Cartella trovata: {folders[0]['name']}")

    # 2. CERCA IL VIDEO NELLA CARTELLA TROVATA
    query_video = f"'{week_folder_id}' in parents and name contains '{nome_file_cercato}' and trashed = false"
    video_results = service.files().list(q=query_video).execute()
    videos = video_results.get('files', [])

    if not videos:
        print(f"Errore: Video '{nome_file_cercato}' non trovato all'interno della cartella.")
        return

    video = videos[0]
    print(f"✅ Video trovato: {video['name']}")

    # 3. CERCA E LEGGI IL PIANO EDITORIALE (EXCEL)
    query_excel = f"'{week_folder_id}' in parents and name contains 'Piano_Editoriale' and trashed = false"
    excel_results = service.files().list(q=query_excel).execute()
    excels = excel_results.get('files', [])

    caption_telegram = f"🎬 Ecco il video di {giorno_it} {fascia}!\n\nSia Gloria a Dio!" 

    if excels:
        excel_file = excels[0]
        print(f"✅ File Excel trovato: {excel_file['name']}")
        
        req_excel = service.files().get_media(fileId=excel_file['id'])
        fh_excel = io.BytesIO()
        dl_excel = MediaIoBaseDownload(fh_excel, req_excel)
        done_excel = False
        while not done_excel:
            _, done_excel = dl_excel.next_chunk()
        fh_excel.seek(0)
        
        try:
            df = pd.read_excel(fh_excel)
            riga = df[df['Nome File'] == video['name']]
            
            if not riga.empty:
                descrizione = str(riga.iloc[0]['Descrizione'])
                hashtag = str(riga.iloc[0]['Hashtag'])
                caption_telegram = f"{descrizione}\n\n{hashtag}"
                
                if len(caption_telegram) > 1024:
                    caption_telegram = caption_telegram[:1000] + "...\n#amen"
                print("✅ Didascalia estratta perfettamente dall'Excel!")
            else:
                print("⚠️ Video non presente nell'Excel, uso didascalia base.")
        except Exception as e:
            print(f"⚠️ Errore Excel: {e}")
    else:
        print("⚠️ Nessun file Excel trovato. Uso didascalia base.")

    # 4. DOWNLOAD VIDEO E INVIO
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
    
    print("Inviando a Telegram...")
    r = requests.post(url, files=files, data=data)
    if r.status_code == 200:
        print("🚀 SUCCESSO: Video e Didascalia pubblicati sul gruppo!")
    else:
        print(f"❌ Errore Telegram: {r.text}")

if __name__ == "__main__":
    main()
