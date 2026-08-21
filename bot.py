import os
import time
import requests
import json
from tavily import TavilyClient
from supabase import create_client, Client

TOKEN = os.environ.get("TELEGRAM_TOKEN", "IL_TUO_TOKEN_TELEGRAM")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "LA_TUA_CHIAVE_OPENAI")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "TUA_CHIAVE_TAVILY")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "IL_TUO_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "IL_TUO_SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
tavily = TavilyClient(api_key=TAVILY_API_KEY)

URL = f"https://api.telegram.org/bot{TOKEN}"

def load_history_from_supabase(chat_id):
    try:
        response = supabase.table("memoria").select("role, content").eq("user_id", str(chat_id)).execute()
        history = [
            {"role": "system", "content": "Sei un assistente finanziario tecnico. Oggi è il 21 agosto 2026. Utilizzi la cronologia della chat come registro permanente per ricordare tutte le informazioni, preferenze e dettagli forniti dall'utente."}
        ]
        if response.data:
            for row in response.data:
                history.append({"role": row["role"], "content": row["content"]})
        return history
    except Exception as e:
        print(f"Errore caricamento memoria: {e}")
        return [{"role": "system", "content": "Sei un assistente finanziario."}]

def save_message_to_supabase(chat_id, role, content):
    try:
        supabase.table("memoria").insert({
            "user_id": str(chat_id),
            "role": role,
            "content": content
        }).execute()
    except Exception as e:
        print(f"Errore salvataggio messaggio: {e}")

def gestisci_portafoglio(chat_id, user_input):
    try:
        check_headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        prompt_trading = f"Analizza questo messaggio: '{user_input}'. Se l'utente vuole registrare un acquisto, estrai ticker, quantita e prezzo_medio. Rispondi SOLO con un JSON: {{\"azione\": \"compra\", \"ticker\": \"TICKER\", \"quantita\": 0, \"prezzo_medio\": 0.0}}. Se non è un acquisto, rispondi con {{\"azione\": \"niente\"}}."
        
        data = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt_trading}]}
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=check_headers, json=data, timeout=10)
        result = json.loads(response.json()["choices"][0]["message"]["content"])
        
        if result.get("azione") == "compra":
            supabase.table("portafoglio").insert({
                "chat_id": str(chat_id),
                "ticker": result["ticker"],
                "quantita": result["quantita"],
                "prezzo_medio": result["prezzo_medio"]
            }).execute()
            return f"✅ Fatto! Ho aggiunto {result['quantita']} unità di {result['ticker']} al tuo portafoglio al prezzo medio di {result['prezzo_medio']}."
        return "Non ho rilevato un ordine di acquisto chiaro."
    except Exception as e:
        return f"Errore nella gestione del portafoglio: {e}"

def ask_openai(chat_id, prompt):
    chat_id_str = str(chat_id)
    
    # 1. Carichiamo la cronologia dalla tabella 'memoria'
    messages = load_history_from_supabase(chat_id_str)
    
    # 2. Aggiungiamo il nuovo messaggio dell'utente alla lista corrente
    messages.append({"role": "user", "content": prompt})
    
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

    if needs_search:
        try:
            search_response = tavily.search(query=prompt, search_depth="advanced", max_results=3)
            context = "Fonti web (2026):\n" + "\n".join([f"- {r['title']}: {r['content']}" for r in search_response.get("results", [])])
            messages.append({"role": "system", "content": context})
        except:
            pass

    data = {"model": "gpt-4o-mini", "messages": messages}
    
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=check_headers, json=data, timeout=30)
        reply = response.json()["choices"][0]["message"]["content"]
        
        # 3. Salviamo il messaggio utente e la risposta del bot sulla tabella 'memoria'
        save_message_to_supabase(chat_id_str, "user", prompt)
        save_message_to_supabase(chat_id_str, "assistant", reply)
        
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
                        
                        if text.lower() == "/reset":
                            try:
                                supabase.table("memoria").delete().eq("user_id", str(chat_id)).execute()
                                send_message(chat_id, "Memoria resettata con successo.")
                            except Exception as e:
                                send_message(chat_id, f"Errore reset: {e}")
                        elif any(k in text.lower() for k in ["ho comprato", "ho acquistato"]):
                            send_message(chat_id, gestisci_portafoglio(chat_id, text))
                        else:
                            send_message(chat_id, ask_openai(chat_id, text))
        except:
            time.sleep(3)

if __name__ == "__main__":
    main()