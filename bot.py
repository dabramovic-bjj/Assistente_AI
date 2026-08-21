import os
import time
import requests
import json
import io
from pypdf import PdfReader
from docx import Document
from tavily import TavilyClient

# Configurazione
TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "TUA_CHIAVE_TAVILY")

tavily = TavilyClient(api_key=TAVILY_API_KEY)
URL = f"https://api.telegram.org/bot{TOKEN}"

chat_histories = {}

def leggi_file_da_telegram(file_id):
    import io
    import pandas as pd
    from pypdf import PdfReader
    from docx import Document
    
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
            for page in reader.pages[:10]: # Legge le prime 10 pag
                testo_estratto += (page.extract_text() or "") + "\n"
        elif ext in ["docx", "doc"]:
            doc = Document(io.BytesIO(file_bytes))
            testo_estratto = "\n".join([p.text for p in doc.paragraphs])
        elif ext in ["xlsx", "xls", "csv"]:
            df = pd.read_excel(io.BytesIO(file_bytes)) if ext != 'csv' else pd.read_csv(io.BytesIO(file_bytes))
            testo_estratto = df.to_string() # Converte la tabella in formato testo
        elif ext in ["txt", "py", "json", "md"]:
            testo_estratto = file_bytes.decode("utf-8", errors="ignore")
        else:
            return f"Formato .{ext} non supportato."
    except Exception as e:
        return f"Errore lettura file: {e}"

    if not testo_estratto.strip():
        return "Il file sembra vuoto o è un'immagine/scansione che non posso leggere direttamente."
        
    return testo_estratto[:15000] # Limite sicurezza

def ask_openai(chat_id, prompt):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [
            {"role": "system", "content": "Sei un assistente virtuale utile e intelligente. Oggi è il 21 agosto 2026."}
        ]
    
    chat_histories[chat_id].append({"role": "user", "content": prompt})

    check_headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    check_data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Rispondi SOLO con 'SI' se la domanda richiede informazioni in tempo reale (notizie, prezzi, meteo), altrimenti 'NO'."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }
    
    needs_search = False
    try:
        check_res = requests.post("https://api.openai.com/v1/chat/completions", headers=check_headers, json=check_data, timeout=10)
        if "SI" in check_res.json()["choices"][0]["message"]["content"].strip().upper():
            needs_search = True
    except:
        pass

    current_messages = list(chat_histories[chat_id])
    if needs_search:
        try:
            search_response = tavily.search(query=prompt, search_depth="advanced", max_results=3)
            context = "Fonti web (2026):\n" + "\n".join([f"- {r['title']}: {r['content']}" for r in search_response.get("results", [])])
            current_messages.insert(1, {"role": "system", "content": context})
        except:
            pass

    data = {"model": "gpt-4o-mini", "messages": current_messages}
    
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=check_headers, json=data, timeout=30)
        reply = response.json()["choices"][0]["message"]["content"]
        chat_histories[chat_id].append({"role": "assistant", "content": reply})
        if len(chat_histories[chat_id]) > 16:
            chat_histories[chat_id] = [chat_histories[chat_id][0]] + chat_histories[chat_id][-15:]
        return reply
    except Exception as e:
        return f"Errore: {e}"

def send_message(chat_id, text):
    try:
        requests.post(f"{URL}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def main():
    print("Bot avviato...")
    offset = None
    processed_updates = set()
    
    while True:
        try:
            updates = requests.get(f"{URL}/getUpdates", params={"timeout": 30, "offset": offset}).json()
            if "result" in updates:
                for update in updates["result"]:
                    if update["update_id"] in processed_updates:
                        continue
                    processed_updates.add(update["update_id"])
                    if len(processed_updates) > 50:
                        processed_updates.pop()
                    
                    offset = update["update_id"] + 1
                    
                    if "message" in update:
                        msg = update["message"]
                        chat_id = msg["chat"]["id"]
                        
                        if "document" in msg:
                            send_message(chat_id, "📥 File ricevuto, lo sto analizzando...")
                            file_id = msg["document"]["file_id"]
                            file_name = msg["document"].get("file_name", "documento")
                            contenuto_file = leggi_file_da_telegram(file_id)
                            
                            if "Errore" in contenuto_file or "non ancora supportato" in contenuto_file:
                                send_message(chat_id, contenuto_file)
                            else:
                                prompt_analisi = f"Analizza il seguente documento ({file_name}). Estrai i dati chiave, fai una sintesi dettagliata e crea un report strutturato:\n\n{contenuto_file}"
                                reply = ask_openai(chat_id, prompt_analisi)
                                send_message(chat_id, reply)
                                
                        elif "text" in msg:
                            text = msg["text"].strip()
                            if text.lower() == "/reset":
                                if chat_id in chat_histories:
                                    del chat_histories[chat_id]
                                send_message(chat_id, "Memoria locale resettata con successo!")
                            else:
                                reply = ask_openai(chat_id, text)
                                send_message(chat_id, reply)
        except:
            time.sleep(3)

if __name__ == "__main__":
    main()