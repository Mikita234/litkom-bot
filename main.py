import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from config import TELEGRAM_TOKEN, DATABASE_PATH
from db import db
from utils import setup_logging, keep_alive
from handlers import admin, leader, common

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)

async def main():
    """Основная функция запуска бота"""
    try:
        # Создаем директорию для базы данных, если её нет
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        # Инициализируем базу данных
        await db.init_db()
        logger.info("База данных инициализирована")
        
        # Создаем бота и диспетчер
        bot = Bot(token=TELEGRAM_TOKEN)
        dp = Dispatcher()
        
        # Регистрируем роутеры
        dp.include_router(admin.router)
        dp.include_router(leader.router)
        dp.include_router(common.router)
        
        # Обработчики команд находятся в handlers/
        
        logger.info("Бот запущен")
        
        # Запускаем бота
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        # Для Render.com используем простой запуск
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
