import os
import time
import requests
import json

TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")
URL = f"https://api.telegram.org/bot{TOKEN}"
DB_FILE = "chat_history.json"

# Caricamento memoria dal file
def load_history():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

# Salvataggio memoria su file
def save_history(history):
    with open(DB_FILE, "w") as f:
        json.dump(history, f)

chat_histories = load_history()

def ask_openai(chat_id, prompt):
    chat_id_str = str(chat_id)
    if chat_id_str not in chat_histories:
        chat_histories[chat_id_str] = [
            {"role": "system", "content": "Sei un assistente virtuale amichevole. Hai una memoria a breve termine. Quando l'utente ti chiede cosa ti ricordi di lui, elenca i dettagli che ti ha detto (come nome o studi) basandoti sulla chat."}
        ]
    
    chat_histories[chat_id_str].append({"role": "user", "content": prompt})
    
    if len(chat_histories[chat_id_str]) > 11:
        chat_histories[chat_id_str] = [chat_histories[chat_id_str][0]] + chat_histories[chat_id_str][-10:]

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "gpt-4o-mini", "messages": chat_histories[chat_id_str]}
    
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=30)
        result = response.json()
        if "choices" in result:
            reply = result["choices"][0]["message"]["content"]
            chat_histories[chat_id_str].append({"role": "assistant", "content": reply})
            save_history(chat_histories) # Salva dopo ogni risposta
            return reply
    except Exception as e:
        return f"Errore: {str(e)}"

def send_message(chat_id, text):
    # PUNTO 3: Aggiunta pulsanti interattivi (Inline Keyboard)
    keyboard = {
        "inline_keyboard": [[
            {"text": "🔄 Reset Memoria", "callback_data": "/reset"},
            {"text": "ℹ️ Info", "callback_data": "info"}
        ]]
    }
    payload = {"chat_id": chat_id, "text": text, "reply_markup": json.dumps(keyboard)}
    requests.post(f"{URL}/sendMessage", json=payload)

def main():
    offset = None
    while True:
        updates = requests.get(f"{URL}/getUpdates", params={"timeout": 30, "offset": offset}).json()
        if "result" in updates:
            for update in updates["result"]:
                offset = update["update_id"] + 1
                
                # Gestione callback dai pulsanti o messaggi testo
                if "callback_query" in update:
                    chat_id = update["callback_query"]["message"]["chat"]["id"]
                    data = update["callback_query"]["data"]
                    if data == "/reset":
                        if str(chat_id) in chat_histories:
                            del chat_histories[str(chat_id)]
                            save_history(chat_histories)
                        send_message(chat_id, "Memoria resettata!")
                    continue
                
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"]
                    if text.strip().lower() == "/reset":
                        if str(chat_id) in chat_histories:
                            del chat_histories[str(chat_id)]
                            save_history(chat_histories)
                        send_message(chat_id, "Memoria resettata!")
                    else:
                        reply = ask_openai(chat_id, text)
                        send_message(chat_id, reply)

if __name__ == "__main__":
    main()