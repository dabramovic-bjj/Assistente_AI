import os
import time
import requests
import json

TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")
URL = f"https://api.telegram.org/bot{TOKEN}"
DB_FILE = "chat_history.json"

# Caricamento memoria dal file JSON (persistente)
def load_history():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# Salvataggio memoria su file JSON
def save_history(history):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(history, f)
    except Exception as e:
        print(f"Errore nel salvataggio della memoria: {e}")

chat_histories = load_history()

def ask_openai(chat_id, prompt):
    chat_id_str = str(chat_id)
    if chat_id_str not in chat_histories:
        chat_histories[chat_id_str] = [
            {"role": "system", "content": "Sei un assistente virtuale amichevole. Hai una memoria a breve termine. Ricordi sempre i dettagli che l'utente ti dice (come il suo nome o cosa studia) e li usi per rispondere in modo naturale."}
        ]
    
    chat_histories[chat_id_str].append({"role": "user", "content": prompt})
    
    # Mantiene gli ultimi messaggi per non sovraccaricare la memoria
    if len(chat_histories[chat_id_str]) > 11:
        chat_histories[chat_id_str] = [chat_histories[chat_id_str][0]] + chat_histories[chat_id_str][-10:]

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "gpt-4o-mini", "messages": chat_histories[chat_id_str]}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=30)
            result = response.json()
            if "choices" in result:
                reply = result["choices"][0]["message"]["content"]
                chat_histories[chat_id_str].append({"role": "assistant", "content": reply})
                save_history(chat_histories) # Salva subito su file
                return reply
            else:
                return f"Errore nella risposta di OpenAI: {result.get('error', 'Risposta non valida')}"
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                return f"Errore di connessione con OpenAI dopo {max_retries} tentativi: {str(e)}"
            time.sleep(2)

    return "Errore imprevisto nella comunicazione con l'IA."

def send_message(chat_id, text):
    try:
        payload = {"chat_id": chat_id, "text": text}
        requests.post(f"{URL}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print(f"Errore nell'invio del messaggio Telegram: {e}")

def main():
    print("Bot avviato con memoria persistente JSON e chat pulita (senza tasti)...")
    offset = None
    
    try:
        initial_updates = requests.get(f"{URL}/getUpdates", timeout=10).json()
        if "result" in initial_updates and initial_updates["result"]:
            offset = initial_updates["result"][-1]["update_id"] + 1
    except Exception:
        pass

    while True:
        try:
            updates = requests.get(f"{URL}/getUpdates", params={"timeout": 30, "offset": offset}).json()
            if "result" in updates:
                for update in updates["result"]:
                    offset = update["update_id"] + 1
                    
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"].strip()
                        text_lower = text.lower()
                        
                        if text_lower == "/reset":
                            if str(chat_id) in chat_histories:
                                del chat_histories[str(chat_id)]
                                save_history(chat_histories)
                            send_message(chat_id, "Memoria resettata! Ricominciamo da capo.")
                        else:
                            ai_reply = ask_openai(chat_id, text)
                            send_message(chat_id, ai_reply)
        except Exception as e:
            print(f"Errore nel ciclo principale: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()