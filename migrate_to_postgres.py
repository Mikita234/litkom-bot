#!/usr/bin/env python3
"""
Миграция с SQLite на PostgreSQL для Render.com
Создает таблицы в PostgreSQL и переносит данные
"""

import asyncio
import asyncpg
import aiosqlite
import os
from config import DATABASE_PATH

# Настройки PostgreSQL для Render.com
DATABASE_URL = os.getenv('DATABASE_URL')  # Render.com автоматически предоставляет

async def migrate_to_postgres():
    """Миграция данных из SQLite в PostgreSQL"""
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL не найден. Убедитесь, что переменная окружения настроена.")
        return
    
    print("🔄 Начинаем миграцию в PostgreSQL...")
    
    # Подключаемся к PostgreSQL
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Создаем таблицы в PostgreSQL
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                tg_id BIGINT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                name TEXT
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS literature (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                category TEXT,
                stock INTEGER NOT NULL DEFAULT 0,
                min_stock INTEGER NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0.0,
                cost REAL NOT NULL DEFAULT 0.0,
                sold INTEGER NOT NULL DEFAULT 0
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS monthly_sales (
                id SERIAL PRIMARY KEY,
                item_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                sold_quantity INTEGER NOT NULL DEFAULT 0,
                total_revenue REAL NOT NULL DEFAULT 0.0,
                total_cost REAL NOT NULL DEFAULT 0.0,
                FOREIGN KEY (item_id) REFERENCES literature(id),
                UNIQUE(item_id, year, month)
            )
        ''')
        
        print("✅ Таблицы PostgreSQL созданы")
        
        # Переносим данные из SQLite (если есть)
        if os.path.exists(DATABASE_PATH):
            print("📦 Переносим данные из SQLite...")
            
            # Подключаемся к SQLite
            sqlite_conn = await aiosqlite.connect(DATABASE_PATH)
            
            # Переносим пользователей
            cursor = await sqlite_conn.execute('SELECT tg_id, role, name FROM users')
            users = await cursor.fetchall()
            
            for user in users:
                await conn.execute(
                    'INSERT INTO users (tg_id, role, name) VALUES ($1, $2, $3) ON CONFLICT (tg_id) DO NOTHING',
                    user[0], user[1], user[2]
                )
            
            # Переносим литературу
            cursor = await sqlite_conn.execute(
                'SELECT name, category, stock, min_stock, price, cost, sold FROM literature'
            )
            items = await cursor.fetchall()
            
            for item in items:
                await conn.execute(
                    '''INSERT INTO literature (name, category, stock, min_stock, price, cost, sold) 
                       VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (name) DO NOTHING''',
                    item[0], item[1], item[2], item[3], item[4], item[5], item[6]
                )
            
            await sqlite_conn.close()
            print(f"✅ Перенесено {len(users)} пользователей и {len(items)} позиций литературы")
        
        print("🎉 Миграция завершена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate_to_postgres())
