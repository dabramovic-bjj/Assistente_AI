import os
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")

URL = f"https://api.telegram.org/bot{TOKEN}"

# Dizionario per memorizzare la cronologia delle chat (Memoria conversazione)
# Chiave: chat_id, Valore: lista di messaggi in formato OpenAI
chat_histories = {}

def ask_openai(chat_id, prompt):
    # Inizializza la cronologia per questa chat se non esiste
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [
            {"role": "system", "content": "Sei un assistente virtuale utile, amichevole e intelligente."}
        ]
    
    # Aggiunge il nuovo messaggio dell'utente alla cronologia
    chat_histories[chat_id].append({"role": "user", "content": prompt})
    
    # Manteniamo solo gli ultimi 10 messaggi per evitare di sovraccaricare la memoria/token
    if len(chat_histories[chat_id]) > 11: # 1 di system + 10 di scambi
        chat_histories[chat_id] = [chat_histories[chat_id][0]] + chat_histories[chat_id][-10:]

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": chat_histories[chat_id]
    }
    
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        result = response.json()
        reply = result["choices"][0]["message"]["content"]
        
        # Aggiunge la risposta dell'assistente alla cronologia
        chat_histories[chat_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        return f"Errore con OpenAI: {str(e)}"

def get_updates(offset=None):
    params = {"timeout": 30, "offset": offset}
    response = requests.get(f"{URL}/getUpdates", params=params)
    return response.json()

def send_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text}
    requests.post(f"{URL}/sendMessage", json=payload)

def main():
    print("Bot avviato con OpenAI e memoria attiva...")
    offset = None
    
    # Svuota i messaggi vecchi accumulati mentre il bot era spento per evitare doppi invii iniziali
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
                    
                    # Chiede a OpenAI la risposta passando la memoria della chat
                    ai_reply = ask_openai(chat_id, text)
                    
                    # Risponde su Telegram
                    send_message(chat_id, ai_reply)

if __name__ == "__main__":
    main()