import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DATABASE_PATH = 'data/litkom.db'
LOG_FILE = 'bot.log'

# Константы для аналитики
DELIVERY_COST = 50.0  # Стоимость доставки в рублях

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не найден в переменных окружения")
