import os
import time
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")

URL = f"https://api.telegram.org/bot{TOKEN}"

# Dizionario per memorizzare la cronologia delle chat
chat_histories = {}

def ask_openai(chat_id, prompt):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [
            {"role": "system", "content": "Sei un assistente IA di livello senior, estremamente competente, chiaro, diretto e amichevole. Aiuti l'utente a risolvere problemi tecnici e organizzativi con precisione."}
        ]
    
    chat_histories[chat_id].append({"role": "user", "content": prompt})
    
    if len(chat_histories[chat_id]) > 11:
        chat_histories[chat_id] = [chat_histories[chat_id][0]] + chat_histories[chat_id][-10:]

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": chat_histories[chat_id]
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=30)
            result = response.json()
            
            if "choices" in result:
                reply = result["choices"][0]["message"]["content"]
                chat_histories[chat_id].append({"role": "assistant", "content": reply})
                return reply
            else:
                return f"Errore nella risposta di OpenAI: {result.get('error', 'Risposta non valida')}"
                
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                return f"Errore di connessione con OpenAI dopo {max_retries} tentativi: {str(e)}"
            time.sleep(2)

    return "Errore imprevisto nella comunicazione con l'IA."

def get_updates(offset=None):
    try:
        params = {"timeout": 30, "offset": offset}
        response = requests.get(f"{URL}/getUpdates", params=params, timeout=35)
        return response.json()
    except Exception:
        return {}

def send_message(chat_id, text):
    try:
        payload = {"chat_id": chat_id, "text": text}
        requests.post(f"{URL}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print(f"Errore nell'invio del messaggio Telegram: {e}")

def main():
    print("Bot avviato con carattere personalizzato, gestione errori e comando reset...")
    offset = None
    
    initial_updates = get_updates()
    if "result" in initial_updates and initial_updates["result"]:
        offset = initial_updates["result"][-1]["update_id"] + 1

    while True:
        updates = get_updates(offset)
        if "result" in updates:
            for update in updates["result"]:
                update_id = update["update_id"]
                offset = update_id + 1
                
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"]
                    
                    if text.strip().lower() == "/reset":
                        if chat_id in chat_histories:
                            del chat_histories[chat_id]
                        send_message(chat_id, "Memoria resettata! Possiamo ricominciare da capo con un nuovo argomento.")
                        continue
                    
                    ai_reply = ask_openai(chat_id, text)
                    send_message(chat_id, ai_reply)

if __name__ == "__main__":
    main()