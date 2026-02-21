# 3. CERCA E LEGGI L'EXCEL O GOOGLE SHEET (Piano Editoriale)
    query_excel = f"'{week_folder_id}' in parents and name contains 'Piano_Editoriale' and trashed = false"
    excel_results = service.files().list(q=query_excel, fields="files(id, name, mimeType)").execute()
    excels = excel_results.get('files', [])

    # Didascalia di base se qualcosa va storto
    caption_telegram = f"🎬 Ecco il video di {giorno_it} {fascia}!\n\nSia Gloria a Dio!" 

    if excels:
        excel_file = excels[0]
        print(f"✅ Foglio trovato: {excel_file['name']}")
        
        # Se è un Google Sheet nativo, lo esporta come Excel, altrimenti lo scarica normalmente
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
            
            # Cerca la riga usando la colonna "File" (come nel tuo Google Sheet)
            if 'File' in df.columns:
                riga = df[df['File'] == video['name']]
            elif 'Nome File' in df.columns:
                riga = df[df['Nome File'] == video['name']]
            else:
                riga = pd.DataFrame() # Colonna non trovata
            
            if not riga.empty:
                descrizione = str(riga.iloc[0]['Descrizione'])
                
                # Se non c'è la colonna Hashtag, non va in errore
                hashtag = str(riga.iloc[0]['Hashtag']) if 'Hashtag' in df.columns else ""
                if hashtag == "nan": hashtag = ""
                
                caption_telegram = f"{descrizione}\n\n{hashtag}".strip()
                
                # Taglio di sicurezza se la didascalia supera i limiti di Telegram
                if len(caption_telegram) > 1024:
                    caption_telegram = caption_telegram[:1000] + "...\n#amen"
                print("✅ Didascalia estratta perfettamente dal Foglio Google!")
            else:
                print(f"⚠️ Video '{video['name']}' non presente nella colonna 'File'. Uso didascalia base.")
        except Exception as e:
            print(f"⚠️ Errore lettura Foglio: {e}")
    else:
        print("⚠️ Nessun Piano Editoriale trovato nella cartella. Uso didascalia base.")
