import os
import time
import requests
import json
import io
import pandas as pd
from pypdf import PdfReader
from docx import Document

# Configurazione
TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")
URL = f"https://api.telegram.org/bot{TOKEN}"

chat_histories = {}
pending_files = {} # Memoria temporanea per il file in attesa

def leggi_file_da_telegram(file_id, file_name):
    file_info = requests.get(f"{URL}/getFile?file_id={file_id}", timeout=10).json()
    if not file_info.get("ok"): return "Errore nel recupero del file."
    
    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
    file_bytes = requests.get(file_url, timeout=20).content
    ext = file_name.split(".")[-1].lower()
    
    testo_estratto = ""
    try:
        if ext == "pdf":
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages[:20]: # Legge fino a 20 pagine per report completi
                testo_estratto += (page.extract_text() or "") + "\n"
        elif ext in ["docx", "doc"]:
            doc = Document(io.BytesIO(file_bytes))
            testo_estratto = "\n".join([p.text for p in doc.paragraphs])
        elif ext in ["xlsx", "xls"]:
            xls = pd.ExcelFile(io.BytesIO(file_bytes))
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, nrows=100)
                testo_estratto += f"\n--- Foglio: {sheet_name} ---\n" + df.to_string() + "\n"
        elif ext == "csv":
            df = pd.read_csv(io.BytesIO(file_bytes), nrows=100)
            testo_estratto = df.to_string()
        elif ext in ["txt", "py", "json", "md", "html"]:
            testo_estratto = file_bytes.decode("utf-8", errors="ignore")
        else:
            return f"Formato .{ext} supportato solo parzialmente o non riconosciuto."
    except Exception as e:
        return f"Errore lettura file: {e}"
    
    return testo_estratto[:20000]

def ask_openai(chat_id, prompt):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [{"role": "system", "content": "Sei un assistente virtuale esperto in analisi dati, sintesi e creazione di report professionali. Oggi è il 21 agosto 2026."}]
    chat_histories[chat_id].append({"role": "user", "content": prompt})
    
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "gpt-4o-mini", "messages": chat_histories[chat_id]}
    
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=60)
        reply = response.json()["choices"][0]["message"]["content"]
        chat_histories[chat_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        return f"Errore di connessione con OpenAI: {e}"

def crea_e_invia_docx_modificato(chat_id, testo_modificato, nome_originale):
    base_name = nome_originale.rsplit('.', 1)[0]
    
    doc = Document()
    for line in testo_modificato.split('\n'):
        doc.add_paragraph(line)
        
    path = f"report_{base_name}.docx"
    doc.save(path)
    
    with open(path, 'rb') as f:
        requests.post(f"{URL}/sendDocument", data={"chat_id": chat_id}, files={"document": f})

def send_message(chat_id, text):
    try:
        # Suddivide i messaggi troppo lunghi per rispettare i limiti di Telegram
        for i in range(0, len(text), 4000):
            requests.post(f"{URL}/sendMessage", json={"chat_id": chat_id, "text": text[i:i+4000]}, timeout=10)
    except: 
        pass

def main():
    print("Bot avviato (Analisi universale & Report Word)...")
    offset = None
    while True:
        try:
            updates = requests.get(f"{URL}/getUpdates", params={"timeout": 30, "offset": offset}).json()
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                
                if "document" in msg:
                    file_name = msg["document"].get("file_name", "documento")
                    pending_files[chat_id] = msg["document"]
                    send_message(chat_id, f"📂 File '{file_name}' ricevuto! Cosa desideri fare? (es: 'Estrai i dati di sintesi e crea un report', 'Analizza le tabelle', oppure 'Modifica il documento...')")
                
                elif "text" in msg:
                    text = msg["text"]
                    if chat_id in pending_files:
                        file_info = pending_files.pop(chat_id)
                        file_name = file_info.get("file_name", "documento")
                        
                        send_message(chat_id, "🔍 Analizzo il file e genero i contenuti...")
                        contenuto = leggi_file_da_telegram(file_info["file_id"], file_name)
                        
                        # Se l'utente chiede un report, una modifica o la creazione di un documento
                        if any(parola in text.lower() for parola in ["modifica", "report", "crea", "scrivi", "genera", "sintesi"]):
                            prompt = f"Istruzioni utente: {text}. Analizza il seguente contenuto estratto, estrapola i dati chiave e genera un report dettagliato/testo aggiornato. Restituisci SOLO il testo finale:\n\n{contenuto}"
                            risultato = ask_openai(chat_id, prompt)
                            crea_e_invia_docx_modificato(chat_id, risultato, file_name)
                            send_message(chat_id, "✅ Ecco il file Word con il report/modifica richiesti!")
                        else:
                            prompt = f"{text}:\n\n{contenuto}"
                            risultato = ask_openai(chat_id, prompt)
                            send_message(chat_id, risultato)
                    elif text == "/reset":
                        chat_histories.pop(chat_id, None)
                        send_message(chat_id, "Memoria resettata.")
        except Exception as e:
            print(f"Errore nel ciclo principale: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()