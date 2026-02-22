import os
import json
import datetime
import requests
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# --- VARIABILI SEGRETE PRESE DA GITHUB SECRETS ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SHEET_ID = "1SYNQjLshCUe0mutORI85EOccI7BiOvjTeUS9Y16YwKQ"

def get_drive_service():
    info = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
    print("\n" + "="*60)
    print(f"👉 LA MIA EMAIL È: {info['client_email']} 👈")
    print("CONDIVIDI LA CARTELLA VIDEO CON QUESTA EMAIL ALTRIMENTI NON LA VEDO!")
    print("="*60 + "\n")
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def pulisci_testo(testo):
    if pd.isna(testo): return ""
    return str(testo).strip().lower().replace(" ", "").replace("_", "").replace("ì", "i").replace("è", "e")

def main():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ ERRORE: TELEGRAM_TOKEN o CHAT_ID mancanti. Inseriscili nei Secrets di GitHub!")
        return

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
    if not folders: 
        print("❌ ERRORE: Nessuna cartella trovata per questa settimana.")
        return
    
    query_video = f"'{folders[0]['id']}' in parents and name contains '{nome_video_cercato}' and trashed = false"
    videos = service.files().list(q=query_video).execute().get('files', [])
    if not videos: 
        print(f"❌ ERRORE: Nessun video trovato con nome contenente {nome_video_cercato}.")
        return
    
    video = videos[0]
    print(f"✅ Video trovato: {video['name']}")

    # 2. CERCA IL FOGLIO E ESTRAI DALLA COLONNA F
    caption_telegram = f"🎬 Ecco il video di {giorno_it} {fascia}!\n\nSia Gloria a Dio!" 
    print(f"🔍 Accesso al foglio Piano_Editoriale_2026...")
    
    try:
        # Essendo pubblico e conoscendo l'ID, lo scarichiamo al volo nel formato CSV
        csv_export_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        df = pd.read_csv(csv_export_url)
        print("✅ Foglio 'Piano_Editoriale_2026' caricato con successo!")

        # Indici delle colonne (In informatica si parte da 0):
        # A=0 (Settimana), C=2 (Giorno), D=3 (Fase), F=5 (Descrizione)
        col_sett = df.columns[0]
        col_giorno = df.columns[2]
        col_fase = df.columns[3]
        
        # Filtriamo le righe per trovare quella giusta
        mask_sett = df[col_sett].astype(str).str.strip() == settimana_anno
        mask_giorno = df[col_giorno].apply(pulisci_testo) == pulisci_testo(giorno_it)
        mask_fase = df[col_fase].apply(pulisci_testo) == pulisci_testo(fascia)
        
        riga = df[mask_sett & mask_giorno & mask_fase]
        
        if not riga.empty:
            # Prende il testo ESATTAMENTE dalla colonna F (Indice 5)
            descrizione = str(riga.iloc[0, 5]).strip() 

            # Verifica che la descrizione non sia vuota o "nan"
            if descrizione and descrizione.lower() != "nan":
                caption_telegram = descrizione
                # Se Telegram ha un limite, accorciamo
                if len(caption_telegram) > 1024: 
                    caption_telegram = caption_telegram[:1000] + "...\n#amen"
                print("✅ Testo estratto con successo dalla Colonna F!")
            else:
                print("⚠️ La colonna F è vuota per questa riga, uso testo di default.")
        else:
            print(f"⚠️ Riga non trovata nel foglio per Settimana {settimana_anno}, {giorno_it}, {fascia}.")
    except Exception as e:
        print(f"⚠️ Errore lettura Foglio Google: {e}")

    # 3. SCARICA IL VIDEO DA DRIVE E INVIA A TELEGRAM
    print("📥 Scaricamento del video in corso...")
    request = service.files().get_media(fileId=video['id'])
    fh_video = io.BytesIO()
    downloader = MediaIoBaseDownload(fh_video, request)
    while not downloader.next_chunk()[1]: pass
    fh_video.seek(0)
    
    print("🚀 Inviando a Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    r = requests.post(url, files={'video': (video['name'], fh_video, 'video/mp4')}, data={'chat_id': CHAT_ID, 'caption': caption_telegram})
    
    if r.status_code == 200:
        print("🌟 SUCCESSO! Video pubblicato su Telegram.")
    else:
        print(f"❌ Errore Telegram: {r.text}")

if __name__ == "__main__":
    main()
