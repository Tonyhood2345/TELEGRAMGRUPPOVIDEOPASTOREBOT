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
        print(f"La mia email è: 👉  {info['client_email']}  👈")
        print("="*60 + "\n")
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Errore caricamento credenziali: {e}")
        return None

def pulisci_testo(testo):
    """Pulisce il testo da spazi e caratteri strani per fare un confronto sicuro."""
    if pd.isna(testo):
        return ""
    return str(testo).strip().lower().replace(" ", "").replace("_", "").replace("ì", "i").replace("è", "e")

def main():
    service = get_drive_service()
    if not service: return

    now = datetime.datetime.now()
    settimana_anno = now.strftime("%V") 
    giorno_sett_en = now.strftime("%A")
    
    giorni_it = {
        "Monday": "Lunedì", "Tuesday": "Martedì", "Wednesday": "Mercoledì",
        "Thursday": "Giovedì", "Friday": "Venerdì", "Saturday": "Sabato", "Sunday": "Domenica"
    }
    
    fascia = "Mattina" if now.hour < 15 else "Pomeriggio"
    giorno_it = giorni_it.get(giorno_sett_en, "Lunedì")
    
    nome_video_cercato = f"{giorno_it.replace('ì','i')}_{'Sera' if fascia == 'Pomeriggio' else 'Mattina'}"
    
    print(f"🔍 Ricerca -> Settimana: {settimana_anno} | Giorno: {giorno_it} | Fase: {fascia}")

    # 1. CERCA LA CARTELLA (Usa il radar globale che funziona bene)
    query_folder = f"mimeType = 'application/vnd.google-apps.folder' and (name = '{settimana_anno}' or name = 'Settimana_{settimana_anno}') and trashed = false"
    results = service.files().list(q=query_folder).execute()
    folders = results.get('files', [])

    if not folders:
        print(f"❌ ERRORE: Nessuna cartella trovata per la settimana {settimana_anno}.")
        return

    week_folder_id = folders[0]['id']
    print(f"✅ Cartella trovata: {folders[0]['name']}")

    # 2. CERCA IL VIDEO SOLO NELLA CARTELLA TROVATA
    query_video = f"'{week_folder_id}' in parents and name contains '{nome_video_cercato}' and trashed = false"
    video_results = service.files().list(q=query_video).execute()
    videos = video_results.get('files', [])

    if not videos:
        print(f"❌ ERRORE: Video '{nome_video_cercato}' non trovato nella cartella {folders[0]['name']}.")
        return

    video = videos[0]
    print(f"✅ Video trovato: {video['name']}")

    # 3. CERCA IL PIANO EDITORIALE *SOLO ED ESCLUSIVAMENTE* NELLA CARTELLA DELLA SETTIMANA
    query_excel = f"'{week_folder_id}' in parents and name contains 'Piano_Editoriale' and trashed = false"
    excel_results = service.files().list(q=query_excel, fields="files(id, name, mimeType)").execute()
    excels = excel_results.get('files', [])

    caption_telegram = f"🎬 Ecco il video di {giorno_it} {fascia}!\n\nSia Gloria a Dio!" 

    if excels:
        excel_file = excels[0]
        print(f"✅ Foglio Editoriale trovato DENTRO la cartella: {excel_file['name']}")
        
        if excel_file['mimeType'] == 'application/vnd.google-apps.spreadsheet':
            req_excel = service.files().export_media(fileId=excel_file['id'], mimeType='text/csv')
            is_csv = True
        else:
            req_excel = service.files().get_media(fileId=excel_file['id'])
            is_csv = False
            
        fh_excel = io.BytesIO()
        dl_excel = MediaIoBaseDownload(fh_excel, req_excel)
        done_excel = False
        while not done_excel:
            _, done_excel = dl_excel.next_chunk()
        fh_excel.seek(0)
        
        try:
            if is_csv or excel_file['name'].endswith('.csv'):
                df = pd.read_csv(fh_excel)
            else:
                df = pd.read_excel(fh_excel)
            
            # Ricerca Dinamica delle Colonne
            col_sett = next((col for col in df.columns if "settimana" in str(col).lower()), None)
            col_giorno = next((col for col in df.columns if "giorno" in str(col).lower()), None)
            col_fase = next((col for col in df.columns if "fase" in str(col).lower()), None)
            col_desc = next((col for col in df.columns if "descrizione" in str(col).lower()), None)
            col_file = next((col for col in df.columns if "file" in str(col).lower()), None)
            
            if col_giorno and col_fase:
                mask_giorno = df[col_giorno].apply(pulisci_testo) == pulisci_testo(giorno_it)
                mask_fase = df[col_fase].apply(pulisci_testo) == pulisci_testo(fascia)
                
                if col_sett:
                    mask_sett = df[col_sett].astype(str).str.strip() == str(int(settimana_anno))
                    riga = df[mask_sett & mask_giorno & mask_fase]
                else:
                    riga = df[mask_giorno & mask_fase]
                
                if not riga.empty:
                    descrizione = str(riga.iloc[0][col_desc]).strip() if col_desc else ""
                    testo_file = str(riga.iloc[0][col_file]).strip() if col_file else ""
                    
                    # Fix automatico per le colonne invertite
                    if ("http" in descrizione or descrizione == "" or descrizione == "nan") and testo_file != "nan" and len(testo_file) > 10:
                        descrizione = testo_file

                    if descrizione and descrizione != "nan":
                        caption_telegram = descrizione.strip()
                        
                        if len(caption_telegram) > 1024:
                            caption_telegram = caption_telegram[:1000] + "...\n#amen"
                        print("✅ Didascalia estratta perfettamente dal Foglio locale!")
                    else:
                        print("⚠️ Didascalia vuota nella riga del foglio.")
                else:
                    print(f"⚠️ Riga Giorno:{giorno_it} Fase:{fascia} NON TROVATA nel foglio.")
            else:
                 print(f"⚠️ Impossibile trovare le colonne nel foglio. Colonne presenti: {list(df.columns)}")

        except Exception as e:
            print(f"⚠️ Errore lettura Foglio: {e}")
    else:
        print("⚠️ Nessun file 'Piano_Editoriale' trovato nella cartella. Uso didascalia base.")

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
