import os
import time
import requests
import json
import io
import pandas as pd
from pypdf import PdfReader
from docx import Document
from tavily import TavilyClient
from fpdf import FPDF

# Configurazione
TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")
URL = f"https://api.telegram.org/bot{TOKEN}"

chat_histories = {}
pending_files = {} # Memoria temporanea per i file in attesa

def leggi_file_da_telegram(file_id):
    file_info = requests.get(f"{URL}/getFile?file_id={file_id}", timeout=10).json()
    if not file_info.get("ok"): return "Errore nel recupero del file."
    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
    file_bytes = requests.get(file_url, timeout=20).content
    ext = file_path.split(".")[-1].lower()
    
    testo_estratto = ""
    try:
        if ext == "pdf":
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages[:10]:
                testo_estratto += (page.extract_text() or "") + "\n"
        elif ext in ["docx", "doc"]:
            doc = Document(io.BytesIO(file_bytes))
            testo_estratto = "\n".join([p.text for p in doc.paragraphs])
        elif ext in ["xlsx", "xls"]:
            xls = pd.ExcelFile(io.BytesIO(file_bytes))
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, nrows=50)
                testo_estratto += f"\n--- Foglio: {sheet_name} ---\n" + df.to_string() + "\n"
    except Exception as e:
        return f"Errore lettura: {e}"
    return testo_estratto[:15000]

def ask_openai(chat_id, prompt):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [{"role": "system", "content": "Sei un assistente virtuale utile."}]
    chat_histories[chat_id].append({"role": "user", "content": prompt})
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "gpt-4o-mini", "messages": chat_histories[chat_id]}
    try:
        # Aumentato a 60 secondi per evitare i timeout con file grandi
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=60)
        reply = response.json()["choices"][0]["message"]["content"]
        chat_histories[chat_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        return f"Errore di connessione: {e}"

def crea_e_invia_file_modificato(chat_id, testo_modificato, nome_originale):
    ext = nome_originale.split('.')[-1].lower()
    base_name = nome_originale.rsplit('.', 1)[0]
    path = ""
    if ext in ['docx', 'doc']:
        doc = Document()
        doc.add_paragraph(testo_modificato)
        path = f"modificato_{base_name}.docx"
        doc.save(path)
    elif ext in ['xlsx', 'xls']:
        try:
            import csv
            f = io.StringIO(testo_modificato)
            reader = csv.reader(f)
            data = list(reader)
            df = pd.DataFrame(data[1:], columns=data[0])
            path = f"modificato_{base_name}.xlsx"
            df.to_excel(path, index=False)
        except: return
    elif ext == 'pdf':
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for line in testo_modificato.encode('latin-1', 'replace').decode('latin-1').split('\n'):
            pdf.cell(200, 10, txt=line, ln=True)
        path = f"modificato_{base_name}.pdf"
        pdf.output(path)
    
    with open(path, 'rb') as f:
        requests.post(f"{URL}/sendDocument", data={"chat_id": chat_id}, files={"document": f})

def send_message(chat_id, text):
    requests.post(f"{URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)

def main():
    offset = None
    while True:
        try:
            updates = requests.get(f"{URL}/getUpdates", params={"timeout": 30, "offset": offset}).json()
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                
                if "document" in msg:
                    pending_files[chat_id] = msg["document"]
                    send_message(chat_id, "File ricevuto! 📄 Cosa vuoi fare? (es: 'Analizza', 'Riassumi', o 'Modifica aggiungendo X')")
                
                elif "text" in msg:
                    text = msg["text"]
                    if chat_id in pending_files:
                        file_info = pending_files.pop(chat_id)
                        contenuto = leggi_file_da_telegram(file_info["file_id"])
                        send_message(chat_id, "✍️ Sto lavorando alla tua richiesta...")
                        
                        if "modifica" in text.lower():
                            prompt = f"Istruzioni: {text}. Restituisci il risultato modificato. Se è un Excel, usa formato CSV."
                            risultato = ask_openai(chat_id, prompt + f"\n\nTesto: {contenuto}")
                            crea_e_invia_file_modificato(chat_id, risultato, file_info.get("file_name", "file"))
                        else:
                            risultato = ask_openai(chat_id, f"{text}:\n\n{contenuto}")
                            send_message(chat_id, risultato)
                    elif text == "/reset":
                        chat_histories.pop(chat_id, None)
                        send_message(chat_id, "Memoria resettata.")
        except: time.sleep(3)

if __name__ == "__main__":
    main()