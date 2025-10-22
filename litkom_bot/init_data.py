"""
Скрипт для инициализации начальных данных в базе
Запускать один раз после первого деплоя
"""

import asyncio
import sys
import os

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import db

async def init_sample_data():
    """Добавление примеров литературы"""
    print("Инициализация базы данных...")
    await db.init_db()
    
    # Примеры литературы
    sample_items = [
        ("Базовый Текст", "Основная литература", 25.0, 2),
        ("Белый буклет", "Буклеты", 15.0, 5),
        ("Новичку", "Для новичков", 30.0, 10),
        ("ЭРКИП", "Специальная литература", 50.0, 3),
        ("Справочник", "Справочная литература", 40.0, 5)
    ]
    
    print("Добавление примеров литературы...")
    for name, category, price, min_stock in sample_items:
        success = await db.add_item(name, category, price, min_stock)
        if success:
            print(f"✅ Добавлена: {name}")
        else:
            print(f"❌ Ошибка добавления: {name}")
    
    # Устанавливаем начальные остатки
    stock_updates = [
        ("Базовый Текст", 2),
        ("Белый буклет", 4),
        ("Новичку", 10),
        ("ЭРКИП", 3),
        ("Справочник", 5)
    ]
    
    print("Установка начальных остатков...")
    for name, stock in stock_updates:
        success = await db.update_stock(name, stock)
        if success:
            print(f"✅ Остаток {name}: {stock} шт.")
        else:
            print(f"❌ Ошибка обновления остатка: {name}")
    
    print("Инициализация завершена!")

if __name__ == "__main__":
    asyncio.run(init_sample_data())
