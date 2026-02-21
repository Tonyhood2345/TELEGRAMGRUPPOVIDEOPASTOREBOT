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
        
        print("\n" + "="*60)
        print("🤖 CIAO! SONO IL BOT DI GITHUB.")
        print("Se non trovo la cartella, vai su Drive, clicca 'Condividi'")
        print("sulla cartella e invitami come 'Editor' usando questa email:")
        print(f"👉  {info['client_email']}  👈")
        print("="*60 + "\n")
        
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Errore caricamento credenziali: {e}")
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
    
    print(f"🔍 Ricerca Globale -> Settimana: {settimana_anno} | File: {nome_file_cercato}")

    # 1. CERCA LA CARTELLA
    query_folder = f"mimeType = 'application/vnd.google-apps.folder' and (name = '{settimana_anno}' or name = 'Settimana_{settimana_anno}') and trashed = false"
    results = service.files().list(q=query_folder).execute()
    folders = results.get('files', [])

    if not folders:
        print(f"❌ ERRORE: Nessuna cartella trovata per la settimana {settimana_anno}.")
        return

    week_folder_id = folders[0]['id']
    print(f"✅ Cartella corretta trovata: {folders[0]['name']}")

    # 2. CERCA IL VIDEO
    query_video = f"'{week_folder_id}' in parents and name contains '{nome_file_cercato}' and trashed = false"
    video_results = service.files().list(q=query_video).execute()
    videos = video_results.get('files', [])

    if not videos:
        print(f"❌ ERRORE: Video '{nome_file_cercato}' non trovato nella cartella.")
        return

    video = videos[0]
    print(f"✅ Video trovato: {video['name']}")

    # 3. CERCA E LEGGI L'EXCEL O GOOGLE SHEET
    query_excel = f"'{week_folder_id}' in parents and name contains 'Piano_Editoriale' and trashed = false"
    excel_results = service.files().list(q=query_excel, fields="files(id, name, mimeType)").execute()
    excels = excel_results.get('files', [])

    caption_telegram = f"🎬 Ecco il video di {giorno_it} {fascia}!\n\nSia Gloria a Dio!" 

    if excels:
        excel_file = excels[0]
        print(f"✅ Foglio trovato: {excel_file['name']}")
        
        if excel_file['mimeType'] == 'application/vnd.google-apps.spreadsheet':
            req_excel = service.files().export_media(fileId=excel_file['id'], mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            req_excel = service.files().get_media(fileId=excel_file['id'])
            
        fh_excel = io.BytesIO()
        dl_excel = MediaIoBaseDownload(fh_excel, req_excel)
        done_excel = False
        while not done_excel:
            _, done_excel = dl_excel.next_chunk()
        fh_excel.seek(0)
        
        try:
            df = pd.read_excel(fh_excel)
            
            # --- NUOVA RICERCA SUPER ELASTICA ---
            # Rendiamo il nome del video "pulito" (togliamo .mp4 e lo mettiamo minuscolo)
            nome_video_pulito = video['name'].replace('.mp4', '').strip().lower()
            
            riga = pd.DataFrame()
            if 'File' in df.columns:
                riga = df[df['File'].astype(str).str.lower().str.contains(nome_video_pulito, na=False)]
            elif 'Nome File' in df.columns:
                riga = df[df['Nome File'].astype(str).str.lower().str.contains(nome_video_pulito, na=False)]
            
            if not riga.empty:
                descrizione = str(riga.iloc[0]['Descrizione'])
                
                # Hashtag opzionale
                hashtag = str(riga.iloc[0]['Hashtag']) if 'Hashtag' in df.columns else ""
                if hashtag == "nan": hashtag = ""
                
                caption_telegram = f"{descrizione}\n\n{hashtag}".strip()
                
                if len(caption_telegram) > 1024:
                    caption_telegram = caption_telegram[:1000] + "...\n#amen"
                print("✅ Didascalia estratta perfettamente dal Foglio Google!")
            else:
                print(f"⚠️ Riga per '{nome_video_pulito}' NON TROVATA nel foglio. Colonne presenti: {list(df.columns)}")
        except Exception as e:
            print(f"⚠️ Errore lettura Foglio: {e}")
    else:
        print("⚠️ Nessun Piano Editoriale trovato nella cartella. Uso didascalia base.")

    # 4. DOWNLOAD VIDEO E INVIO A TELEGRAM
    request = service.files().get_media(fileId=video['id'])
    fh_video = io.BytesIO()
    downloader = MediaIoBaseDownload(fh_video, request)
    done_video = False
    while not done_video:
        status, done_video = downloader.next_chunk()
        if status:
            print(f"📥 Download Video: {int(status.progress() * 100)}%")
    
    fh_video.seek(0)
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    files = {'video': (video['name'], fh_video, 'video/mp4')}
    data = {'chat_id': CHAT_ID, 'caption': caption_telegram}
    
    print("🚀 Inviando tutto a Telegram...")
    r = requests.post(url, files=files, data=data)
    if r.status_code == 200:
        print("🌟 SUCCESSO: Video e Didascalia pubblicati sul gruppo!")
    else:
        print(f"❌ Errore Telegram: {r.text}")

if __name__ == "__main__":
    main()
