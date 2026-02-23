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
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        print("❌ ERRORE: Variabile GOOGLE_APPLICATION_CREDENTIALS mancante.")
        return None
        
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
    
    # --- LOGICA DI SINCRONIZZAZIONE CON COLAB v21.13 ---
    # 1. Per il FOGLIO usiamo il numero senza zero (es. "9")
    settimana_sheet = str(int(now.strftime("%V"))) 
    
    # 2. Per la CARTELLA DRIVE usiamo il numero con lo zero (es. "09")
    settimana_folder = now.strftime("%V")
    
    giorno_sett_en = now.strftime("%A")
    giorni_it = {"Monday": "Lunedì", "Tuesday": "Martedì", "Wednesday": "Mercoledì", "Thursday": "Giovedì", "Friday": "Venerdì", "Saturday": "Sabato", "Sunday": "Domenica"}
    
    # 3. Fascia Oraria: Colab scrive "Pomeriggio", quindi cerchiamo "Pomeriggio"
    fascia = "Mattina" if now.hour < 15 else "Pomeriggio"
    giorno_it = giorni_it.get(giorno_sett_en, "Lunedì")
    
    # 4. Nome File: Deve coincidere con Colab (es. Lunedi_Pomeriggio)
    nome_video_cercato = f"{giorno_it.replace('ì','i')}_{fascia}"
    
    print(f"🔍 CONFIGURAZIONE DI OGGI:")
    print(f"   📅 Settimana Sheet: {settimana_sheet}")
    print(f"   📂 Settimana Folder: {settimana_folder}")
    print(f"   📆 Giorno: {giorno_it} ({fascia})")
    print(f"   🎥 File cercato: {nome_video_cercato}")

    # 1. CERCA LA CARTELLA (Usa settimana_folder "09")
    query_folder = f"mimeType = 'application/vnd.google-apps.folder' and name contains '{settimana_folder}' and trashed = false"
    folders = service.files().list(q=query_folder).execute().get('files', [])
    if not folders: 
        print(f"❌ ERRORE: Nessuna cartella trovata per la settimana '{settimana_folder}'.")
        return
    
    # 2. CERCA IL VIDEO NELLA CARTELLA
    query_video = f"'{folders[0]['id']}' in parents and name contains '{nome_video_cercato}' and trashed = false"
    videos = service.files().list(q=query_video).execute().get('files', [])
    if not videos: 
        print(f"❌ ERRORE: Nessun video trovato con nome contenente '{nome_video_cercato}' nella cartella '{folders[0]['name']}'.")
        return
    
    video = videos[0]
    print(f"✅ Video trovato su Drive: {video['name']}")

    # 3. CERCA IL FOGLIO E ESTRAI DALLA COLONNA F
    caption_telegram = f"🎬 Ecco il video di {giorno_it} {fascia}!\n\nSia Gloria a Dio!" 
    print(f"🔍 Accesso al foglio Piano_Editoriale_2026...")
    
    try:
        csv_export_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        # dtype=str è FONDAMENTALE: legge tutto come testo così "09" e "9" non si confondono
        df = pd.read_csv(csv_export_url, dtype=str) 
        print("✅ Foglio caricato e letto correttamente!")

        # MAPPATURA COLONNE COLAB v21.13 -> GITHUB
        # A(0)=Settimana, B(1)=Data, C(2)=Giorno, D(3)=Fase, F(5)=Descrizione
        
        # Filtriamo le righe
        mask_sett = df.iloc[:, 0].str.strip() == settimana_sheet
        mask_giorno = df.iloc[:, 2].apply(pulisci_testo) == pulisci_testo(giorno_it)
        mask_fase = df.iloc[:, 3].apply(pulisci_testo) == pulisci_testo(fascia)
        
        riga = df[mask_sett & mask_giorno & mask_fase]
        
        if not riga.empty:
            # Prende il testo dalla colonna F (Indice 5)
            descrizione = str(riga.iloc[0, 5]).strip() 

            if descrizione and descrizione.lower() != "nan":
                caption_telegram = descrizione
                # Limite Telegram 1024 caratteri
                if len(caption_telegram) > 1024: 
                    caption_telegram = caption_telegram[:1000] + "...\n#amen"
                print("✅ Testo estratto con successo dalla Colonna F!")
            else:
                print("⚠️ La colonna F è vuota, uso caption di default.")
        else:
            print(f"⚠️ Riga non trovata nel foglio per: Settimana {settimana_sheet}, {giorno_it}, {fascia}.")
            print("💡 Suggerimento: Verifica che Colab abbia scritto la riga e che la data coincida.")
    except Exception as e:
        print(f"⚠️ Errore lettura Foglio Google: {e}")

    # 4. SCARICA E INVIA
    print("📥 Scaricamento del video in corso...")
    request = service.files().get_media(fileId=video['id'])
    fh_video = io.BytesIO()
    downloader = MediaIoBaseDownload(fh_video, request)
    while not downloader.next_chunk()[1]: pass
    fh_video.seek(0)
    
    print("🚀 Inviando a Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    files = {'video': (video['name'], fh_video, 'video/mp4')}
    data = {'chat_id': CHAT_ID, 'caption': caption_telegram}
    
    r = requests.post(url, files=files, data=data)
    
    if r.status_code == 200:
        print("🌟 SUCCESSO! Video pubblicato su Telegram.")
    else:
        print(f"❌ Errore Telegram: {r.text}")

if __name__ == "__main__":
    main()
