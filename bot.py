import os
import time
import requests
import json
from tavily import TavilyClient

TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "TUA_CHIAVE_TAVILY")
URL = f"https://api.telegram.org/bot{TOKEN}"
DB_FILE = "chat_history.json"

tavily = TavilyClient(api_key=TAVILY_API_KEY)

def load_history():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(history):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Errore nel salvataggio della memoria: {e}")

chat_histories = load_history()

def ask_openai(chat_id, prompt):
    chat_id_str = str(chat_id)
    if chat_id_str not in chat_histories:
        chat_histories[chat_id_str] = [
            {"role": "system", "content": "Sei un assistente virtuale amichevole e intelligente. Oggi è il 21 agosto 2026. Quando ti vengono fornite informazioni da una ricerca web, usale per dare risposte aggiornate e precise citando le fonti."}
        ]
    
    messages = list(chat_histories[chat_id_str])
    
    check_headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    check_data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Rispondi SOLO con la parola 'SI' se la domanda richiede informazioni in tempo reale, notizie recenti, prezzi attuali, meteo o dati aggiornati. Rispondi SOLO con 'NO' altrimenti."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }
    
    needs_search = False
    try:
        check_res = requests.post("https://api.openai.com/v1/chat/completions", headers=check_headers, json=check_data, timeout=10)
        answer = check_res.json()["choices"][0]["message"]["content"].strip().upper()
        if "SI" in answer:
            needs_search = True
    except Exception as e:
        print(f"Errore nel controllo della ricerca: {e}")

    if needs_search:
        try:
            search_response = tavily.search(query=prompt, search_depth="advanced", max_results=3)
            results = search_response.get("results", [])
            if results:
                context = "Fonti web ufficiali e aggiornate (Anno 2026):\n"
                for r in results:
                    title = r.get('title', '')
                    content = r.get('content', '')
                    url = r.get('url', '')
                    context += f"- [{title}]({url}): {content}\n"
                
                messages.append({"role": "system", "content": context})
        except Exception as e:
            print(f"Errore durante la ricerca Tavily: {e}")

    messages.append({"role": "user", "content": prompt})
    
    if len(messages) > 12:
        messages = [messages[0]] + messages[-11:]

    data = {"model": "gpt-4o-mini", "messages": messages}
    
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=check_headers, json=data, timeout=30)
        result = response.json()
        if "choices" in result:
            reply = result["choices"][0]["message"]["content"]
            chat_histories[chat_id_str].append({"role": "user", "content": prompt})
            chat_histories[chat_id_str].append({"role": "assistant", "content": reply})
            save_history(chat_histories)
            return reply
    except Exception as e:
        return f"Errore di connessione con OpenAI: {str(e)}"

def send_message(chat_id, text):
    try:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        requests.post(f"{URL}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print(f"Errore nell'invio del messaggio Telegram: {e}")

def main():
    print("Bot avviato con fix anti-doppio messaggio...")
    offset = None
    
    # Sincronizzazione iniziale per saltare i messaggi vecchi
    try:
        initial_updates = requests.get(f"{URL}/getUpdates", timeout=10).json()
        if "result" in initial_updates and initial_updates["result"]:
            offset = initial_updates["result"][-1]["update_id"] + 1
    except Exception:
        pass

    while True:
        try:
            # Richiesta a lungo polling con offset aggiornato
            updates = requests.get(f"{URL}/getUpdates", params={"timeout": 30, "offset": offset}).json()
            
            if "result" in updates:
                for update in updates["result"]:
                    update_id = update["update_id"]
                    # Spostiamo subito l'offset in avanti così Telegram sa che abbiamo preso in carico questo update
                    offset = update_id + 1

                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"].strip()
                        
                        if text.lower() == "/reset":
                            if str(chat_id) in chat_histories:
                                del chat_histories[str(chat_id)]
                                save_history(chat_histories)
                            send_message(chat_id, "Memoria resettata! Ora non so più nulla di te, ricominciamo.")
                        else:
                            ai_reply = ask_openai(chat_id, text)
                            send_message(chat_id, ai_reply)
                            
        except Exception as e:
            print(f"Errore nel ciclo principale: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()