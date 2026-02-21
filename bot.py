import os
import json
import datetime
import requests
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

TELEGRAM_TOKEN = "8083806105:AAGQTsM8kmogmc4UMkMODnsT_5HK-viO7n4"
CHAT_ID = "-1003619559876"

def get_drive_service():
    info = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
    print("\n" + "="*60)
    print(f"👉 LA MIA EMAIL È: {info['client_email']} 👈")
    print("CONDIVIDI IL FILE EXCEL CON QUESTA EMAIL ALTRIMENTI NON LO VEDO!")
    print("="*60 + "\n")
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def pulisci_testo(testo):
    if pd.isna(testo): return ""
    return str(testo).strip().lower().replace(" ", "").replace("_", "").replace("ì", "i").replace("è", "e")

def main():
    service = get_drive_service()
    if not service: return

    now = datetime.datetime.now()
    settimana_anno = str(int(now.strftime("%V"))) # Rimuove lo zero iniziale (es. "08" -> "8")
    giorno_sett_en = now.strftime("%A")
    
    giorni_it = {"Monday": "Lunedì", "Tuesday": "Martedì", "Wednesday": "Mercoledì", "Thursday": "Giovedì", "Friday": "Venerdì", "Saturday": "Sabato", "Sunday": "Domenica"}
    fascia = "Mattina" if now.hour < 15 else "Pomeriggio"
    giorno_it = giorni_it.get(giorno_sett_en, "Lunedì")
    
    nome_video_cercato = f"{giorno_it.replace('ì','i')}_{'Sera' if fascia == 'Pomeriggio' else 'Mattina'}"
    print(f"🔍 Cerco -> Settimana: {settimana_anno} | Giorno: {giorno_it} | Fase: {fascia}")

    # 1. CERCA LA CARTELLA E IL VIDEO
    query_folder = f"mimeType = 'application/vnd.google-apps.folder' and name contains '{now.strftime('%V')}' and trashed = false"
    folders = service.files().list(q=query_folder).execute().get('files', [])
    if not folders: return print("❌ ERRORE: Nessuna cartella trovata.")
    
    query_video = f"'{folders[0]['id']}' in parents and name contains '{nome_video_cercato}' and trashed = false"
    videos = service.files().list(q=query_video).execute().get('files', [])
    if not videos: return print("❌ ERRORE: Nessun video trovato.")
    video = videos[0]
    print(f"✅ Video trovato: {video['name']}")

    # 2. CERCA IL FOGLIO IN TUTTO IL DRIVE (Devi averlo condiviso con l'email del bot!)
    query_excel = "(mimeType='application/vnd.google-apps.spreadsheet' or mimeType='text/csv' or name contains 'Piano') and trashed = false"
    excels = service.files().list(q=query_excel, fields="files(id, name, mimeType)", orderBy="modifiedTime desc").execute().get('files', [])

    caption_telegram = f"🎬 Ecco il video di {giorno_it} {fascia}!\n\nSia Gloria a Dio!" 

    if not excels:
        print("🚨 ATTENZIONE: NESSUN FOGLIO TROVATO! 🚨")
        print("Motivo: Non hai cliccato 'Condividi' sul file Excel e non hai inserito la mia email.")
    else:
        excel_file = excels[0]
        print(f"✅ Foglio trovato: {excel_file['name']}")
        
        if excel_file['mimeType'] == 'application/vnd.google-apps.spreadsheet':
            req_excel = service.files().export_media(fileId=excel_file['id'], mimeType='text/csv')
        else:
            req_excel = service.files().get_media(fileId=excel_file['id'])
            
        fh_excel = io.BytesIO()
        dl_excel = MediaIoBaseDownload(fh_excel, req_excel)
        while not dl_excel.next_chunk()[1]: pass
        fh_excel.seek(0)
        
        try:
            df = pd.read_csv(fh_excel) if 'csv' in excel_file['mimeType'] or excel_file['name'].endswith('.csv') else pd.read_excel(fh_excel)
            
            col_sett = next((col for col in df.columns if "settimana" in str(col).lower()), None)
            col_giorno = next((col for col in df.columns if "giorno" in str(col).lower()), None)
            col_fase = next((col for col in df.columns if "fase" in str(col).lower()), None)
            col_desc = next((col for col in df.columns if "descrizione" in str(col).lower()), None)
            col_file = next((col for col in df.columns if "file" in str(col).lower()), None)
            
            mask_sett = df[col_sett].astype(str).str.strip() == settimana_anno if col_sett else True
            mask_giorno = df[col_giorno].apply(pulisci_testo) == pulisci_testo(giorno_it)
            mask_fase = df[col_fase].apply(pulisci_testo) == pulisci_testo(fascia)
            
            riga = df[mask_sett & mask_giorno & mask_fase]
            if not riga.empty:
                descrizione = str(riga.iloc[0][col_desc]).strip() if col_desc else ""
                testo_file = str(riga.iloc[0][col_file]).strip() if col_file else ""
                
                # Fix intelligenza artificiale per colonne sfalsate
                if ("http" in descrizione or descrizione == "nan" or descrizione == "") and len(testo_file) > 10 and testo_file != "nan":
                    descrizione = testo_file

                if descrizione and descrizione != "nan":
                    caption_telegram = descrizione.strip()
                    if len(caption_telegram) > 1024: caption_telegram = caption_telegram[:1000] + "...\n#amen"
                    print("✅ Testo estratto con successo!")
            else:
                print(f"⚠️ Riga non trovata nel foglio per Settimana {settimana_anno}, {giorno_it}, {fascia}.")
        except Exception as e:
            print(f"⚠️ Errore lettura: {e}")

    # 3. SCARICA E INVIA
    print("📥 Scaricamento in corso...")
    request = service.files().get_media(fileId=video['id'])
    fh_video = io.BytesIO()
    downloader = MediaIoBaseDownload(fh_video, request)
    while not downloader.next_chunk()[1]: pass
    fh_video.seek(0)
    
    print("🚀 Inviando a Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    r = requests.post(url, files={'video': (video['name'], fh_video, 'video/mp4')}, data={'chat_id': CHAT_ID, 'caption': caption_telegram})
    print("🌟 SUCCESSO!" if r.status_code == 200 else f"❌ Errore Telegram: {r.text}")

if __name__ == "__main__":
    main()
