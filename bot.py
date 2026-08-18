import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from openai import OpenAI

# Configurazione dei log
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Legge i token in modo sicuro dalle variabili d'ambiente (sia locale che cloud)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Inizializza il client OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_name = update.effective_user.first_name
    
    logging.info(f"Ricevuto messaggio da {user_name}: {user_message}")

    # Risposta temporanea di test
    risposta_test = f"Ciao {user_name}! Ho ricevuto il tuo messaggio: '{user_message}'. Il sistema sul Cloud è attivo!"
    
    await update.message.reply_text(risposta_test)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Il bot è avviato e in ascolto...")
    app.run_polling()