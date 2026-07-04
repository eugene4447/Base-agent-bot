import os
import requests
from bs4 import BeautifulSoup
import telebot
from groq import Groq
from flask import Flask
from web3 import Web3

app = Flask(__name__)

# --- НАСТРОЙКИ (Используют переменные окружения) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BASE_RPC_URL = os.getenv("BASE_RPC_URL") # Теперь берется из настроек Vercel/сервера
CONTRACT_ADDRESS = "0x41A3Afde2a4B1c7cf3481844cD4De43Dd9558a48"
TARGET_CHANNEL_ID = "@BasedXNews" 

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

def check_contract_via_rpc():
    try:
        w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
        contract_abi = [
            {"constant": True, "inputs": [], "name": "isActive", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
            {"constant": True, "inputs": [], "name": "energyBalance", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}
        ]
        contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
        
        is_active = contract.functions.isActive().call()
        energy = contract.functions.energyBalance().call()
        
        print(f"WEB3_DEBUG: Active={is_active}, Energy={energy}")
        return is_active and (energy > 0)
    except Exception as e:
        print(f"WEB3_ERROR: {e}")
        return False

def get_twitter_news():
    """Сбор новостей через Google News RSS"""
    tweets_data = []
    google_rss_url = "https://news.google.com/rss/search?q=Base+Network+blockchain&hl=en-US&gl=US&ceid=US:en"
    
    try:
        res = requests.get(google_rss_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, 'xml')
            items = soup.find_all('item')
            for item in items[:2]:
                tweets_data.append({"text": item.title.text, "link": item.link.text})
            print(f"DEBUG: Успешно получили {len(tweets_data)} новостей из Google News")
    except Exception as e:
        print(f"DEBUG: Ошибка Google News: {e}")
        
    return tweets_data

def filter_with_groq(tweets_data):
    try:
        content_text = ""
        for t in tweets_data:
            content_text += f"Title: {t['text']}\n"
        
        content_text = content_text[:1000]

        chat = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a news reporter for Base Network. Summarize the news about Base Network. Respond in one short, engaging paragraph. If not related to Base, say NO_NEWS."},
                {"role": "user", "content": content_text}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.3
        )
        return chat.choices[0].message.content
    except Exception as e:
        print(f"DEBUG: Ошибка Groq: {e}")
        return "NO_NEWS"

@app.route('/')
def home():
    return "Base AI Agent Server is Running!", 200

@app.route('/api/cron')
def index():
    if not check_contract_via_rpc():
        return "Node Offline or Energy Low", 200

    tweets_data = get_twitter_news()
    if not tweets_data:
        return "No news found", 200

    clean_news = filter_with_groq(tweets_data)
    
    if clean_news and clean_news.strip() != "NO_NEWS":
        try:
            bot.send_message(TARGET_CHANNEL_ID, f"🤖 **Base Network Update:**\n\n{clean_news}", parse_mode="Markdown")
            return "Success: News Posted", 200
        except Exception as e:
            return f"Telegram Error: {str(e)}", 200

    return "No new updates", 200

if __name__ == "__main__":
    app.run(debug=True)
