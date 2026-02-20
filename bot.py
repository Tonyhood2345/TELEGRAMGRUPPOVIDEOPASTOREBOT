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
# Questa è la cartella "PastoreAI_2026_Archivio"
FOLDER_ID_ROOT = "1u7VGIK8OPFcuNOBhEtTG1UHCoFlwyVhA"

def get_drive_service():
    try:
        info = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Errore caricamento credenziali: {e}")
        return None

def main():
    service = get_drive_service()
    if not service: return

    now = datetime.datetime.now()
    settimana_anno = now.strftime("%V") # Es: "08"
    giorno_settimana = now.strftime("%A").upper()
    fascia = "MATTINA" if now.hour < 15 else "POMERIGGIO"
    
    giorni_it = {
        "MONDAY": "LUNEDI", "TUESDAY": "MARTEDI", "WEDNESDAY": "MERCOLEDI",
        "THURSDAY": "GIOVEDI", "FRIDAY": "VENERDI", "SATURDAY": "SABATO", "SUNDAY": "DOMENICA"
    }
    
    nome_giorno = giorni_it.get(giorno_settimana, "LUNEDI")
    nome_file_cercato = f"{nome_giorno}_{fascia}"
    
    print(f"--- AVVIO RICERCA ---")
    print(f"Settimana: {settimana_anno} | Giorno: {nome_giorno} | Fascia: {fascia}")

    # 1. CERCA LA CARTELLA DELLA SETTIMANA (Ricerca broad)
    query_folder = f"'{FOLDER_ID_ROOT}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query_folder).execute()
    folders = results.get('files', [])

    week_folder_id = None
    for f in folders:
        # Se il nome della cartella contiene "08", la prendiamo
        if settimana_anno in f['name']:
            week_folder_id = f['id']
            print(f"✅ Cartella settimana trovata: {f['name']} (ID: {week_folder_id})")
            break

    if not week_folder_id:
        print(f"❌ ERRORE: Nessuna cartella trovata che contiene '{settimana_anno}' dentro PastoreAI_2026_Archivio")
        print(f"Cartelle trovate in root: {[f['name'] for f in folders]}")
        return

    # 2. CERCA IL VIDEO
    # Cerchiamo un file che contenga il nome (es: "VENERDI_MATTINA")
    query_video = f"'{week_folder_id}' in parents and name contains '{nome_file_cercato}' and trashed = false"
    video_results = service.files().list(q=query_video).execute()
    videos = video_results.get('files', [])

    if not videos:
        print(f"❌ ERRORE: Nessun video trovato con nome '{nome_file_cercato}' nella cartella {sett
