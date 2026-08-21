import os
import time
import requests
import json
from tavily import TavilyClient

TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "TUA_CHIAVE_TAVILY")

tavily = TavilyClient(api_key=TAVILY_API_KEY)
URL = f"https://api.telegram.org/bot{TOKEN}"

# Dizionario in memoria per memorizzare la cronologia delle chat attive
chat_histories = {}

def ask_openai(chat_id, prompt):
    # Inizializza la cronologia per questa chat se non esiste
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [
            {"role": "system", "content": "Sei un assistente virtuale utile e intelligente. Oggi è il 21 agosto 2026."}
        ]
    
    # Aggiungi il nuovo messaggio dell'utente alla cronologia locale
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

    # Copia temporanea dei messaggi per includere eventualmente la ricerca web
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
        
        # Salva la risposta del bot nella cronologia ufficiale della chat
        chat_histories[chat_id].append({"role": "assistant", "content": reply})
        
        # Mantieni la cronologia corta (massimo ultimi 15 messaggi per non appesantire)
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
    while True:
        try:
            updates = requests.get(f"{URL}/getUpdates", params={"timeout": 30, "offset": offset}).json()
            if "result" in updates:
                for update in updates["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"].strip()
                        
                        # Gestione del comando /reset in memoria locale
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