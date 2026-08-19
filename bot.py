import os
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")

URL = f"https://api.telegram.org/bot{TOKEN}"

def ask_openai(prompt):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    result = response.json()
    try:
        return result["choices"][0]["message"]["content"]
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
    print("Bot avviato con OpenAI...")
    offset = None
    while True:
        updates = get_updates(offset)
        if "result" in updates:
            for update in updates["result"]:
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"]["text"]
                    
                    # Chiede a OpenAI la risposta
                    ai_reply = ask_openai(text)
                    
                    # Risponde su Telegram
                    send_message(chat_id, ai_reply)

if __name__ == "__main__":
    main()