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

def ask_openai(chat_id, prompt, image_url=None):
    chat_id_str = str(chat_id)
    if chat_id_str not in chat_histories:
        chat_histories[chat_id_str] = [
            {"role": "system", "content": "Sei un assistente virtuale amichevole ed esperto di economia. Ricordi che l'utente si chiama Matteo, ha 21 anni e studia economia. Quando ti vengono fornite informazioni da una ricerca web, usale per dare risposte aggiornate e precise citando le fonti."}
        ]
    
    messages = list(chat_histories[chat_id_str])
    
    # Gestione della richiesta se include un'immagine o richiede ricerca
    needs_search = False
    if not image_url:
        check_headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        check_data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Rispondi SOLO con la parola 'SI' se la domanda richiede informazioni in tempo reale, notizie recenti, prezzi attuali, meteo o dati aggiornati. Rispondi SOLO con 'NO' altrimenti."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0
        }
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
                    context = "Fonti web ufficiali e aggiornate:\n"
                    for r in results:
                        title = r.get('title', '')
                        content = r.get('content', '')
                        url = r.get('url', '')
                        context += f"- [{title}]({url}): {content}\n"
                    messages.append({"role": "system", "content": context})
            except Exception as e:
                print(f"Errore durante la ricerca Tavily: {e}")

    # Costruiamo il messaggio utente (supporto testo o multimediale con immagine)
    if image_url:
        user_content = [
            {"type": "text", "text": prompt if prompt else "Analizza questa immagine."},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
    else:
        user_content = prompt

    messages.append({"role": "user", "content": user_content})
    
    if len(messages) > 12:
        messages = [messages[0]] + messages[-11:]

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "gpt-4o-mini", "messages": messages}
    
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=30)
        result = response.json()
        if "choices" in result:
            reply = result["choices"][0]["message"]["content"]
            # Salviamo una versione testuale nello storico per evitare conflitti con la struttura dell'immagine
            chat_histories[chat_id_str].append({"role": "user", "content": prompt if prompt else "[Immagine inviata]"})
            chat_histories[chat_id_str].append({"role": "assistant", "content": reply})
            save_history(chat_histories)
            return reply
    except Exception as e:
        return f"Errore di connessione con OpenAI: {str(e)}"

def send_message(chat_id, text):
    try:
        payload = {"chat_id": chat_id, "text": text}
        requests.post(f"{URL}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print(f"Errore nell'invio del messaggio Telegram: {e}")

def get_telegram_file_url(file_id):
    try:
        file_info = requests.get(f"{URL}/getFile?file_id={file_id}", timeout=10).json()
        if "result" in file_info:
            file_path = file_info["result"]["file_path"]
            return f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
    except Exception as e:
        print(f"Errore nel recupero del file Telegram: {e}")
    return None

def main():
    print("Bot avanzato avviato con successo...")
    offset = None
    
    try:
        initial_updates = requests.get(f"{URL}/getUpdates", timeout=10).json()
        if "result" in initial_updates and initial_updates["result"]:
            offset = initial_updates["result"][-1]["update_id"] + 1
    except Exception:
        pass

    processed_updates = set()

    while True:
        try:
            updates = requests.get(f"{URL}/getUpdates", params={"timeout": 30, "offset": offset}).json()
            if "result" in updates:
                for update in updates["result"]:
                    update_id = update["update_id"]
                    offset = update_id + 1
                    
                    if update_id in processed_updates:
                        continue
                    processed_updates.add(update_id)
                    if len(processed_updates) > 100:
                        processed_updates.pop()

                    chat_id = update["message"]["chat"]["id"] if "message" in update else None
                    if not chat_id:
                        continue

                    message = update["message"]
                    
                    # Gestione Comando /reset
                    if "text" in message and message["text"].strip().lower() == "/reset":
                        if str(chat_id) in chat_histories:
                            del chat_histories[str(chat_id)]
                            save_history(chat_histories)
                        send_message(chat_id, "Memoria resettata! Ricominciamo da capo.")
                    
                    # Gestione Comando /mercati (Flash mercati finanziari)
                    elif "text" in message and message["text"].strip().lower() == "/mercati":
                        send_message(chat_id, "Analizzo la situazione dei mercati finanziari globali...")
                        market_query = "ultime notizie borse mercati finanziari andamento oggi"
                        ai_reply = ask_openai(chat_id, market_query)
                        send_message(chat_id, ai_reply)

                    # Gestione Immagini inviate dall'utente
                    elif "photo" in message:
                        # Prende la foto a risoluzione più alta (l'ultima della lista)
                        photo = message["photo"][-1]
                        file_id = photo["file_id"]
                        caption = message.get("caption", "Analizza questa immagine.")
                        
                        image_url = get_telegram_file_url(file_id)
                        if image_url:
                            ai_reply = ask_openai(chat_id, caption, image_url=image_url)
                            send_message(chat_id, ai_reply)
                        else:
                            send_message(chat_id, "Non sono riuscito a elaborare l'immagine.")

                    # Gestione Messaggi di testo normali
                    elif "text" in message:
                        text = message["text"].strip()
                        ai_reply = ask_openai(chat_id, text)
                        send_message(chat_id, ai_reply)

        except Exception as e:
            print(f"Errore nel ciclo principale: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()