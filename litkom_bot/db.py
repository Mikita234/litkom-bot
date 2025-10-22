import aiosqlite
import logging
from typing import List, Dict, Optional, Tuple
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Создание таблицы пользователей
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tg_id INTEGER UNIQUE NOT NULL,
                        role TEXT NOT NULL DEFAULT 'user',
                        name TEXT
                    )
                ''')
                
                # Создание таблицы литературы
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS literature (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        category TEXT,
                        stock INTEGER NOT NULL DEFAULT 0,
                        min_stock INTEGER NOT NULL DEFAULT 0,
                        price REAL NOT NULL DEFAULT 0.0,
                        sold INTEGER NOT NULL DEFAULT 0
                    )
                ''')
                
                await db.commit()
                logger.info("База данных инициализирована успешно")
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    async def add_user(self, tg_id: int, role: str, name: str = None) -> bool:
        """Добавление пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT OR REPLACE INTO users (tg_id, role, name) VALUES (?, ?, ?)',
                    (tg_id, role, name)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False
    
    async def get_user_role(self, tg_id: int) -> Optional[str]:
        """Получение роли пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT role FROM users WHERE tg_id = ?', (tg_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logger.error(f"Ошибка получения роли пользователя: {e}")
            return None
    
    async def is_admin(self, tg_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        role = await self.get_user_role(tg_id)
        return role == 'admin'
    
    async def is_leader(self, tg_id: int) -> bool:
        """Проверка, является ли пользователь ведущим"""
        role = await self.get_user_role(tg_id)
        return role in ['admin', 'leader']
    
    async def add_item(self, name: str, category: str, price: float, min_stock: int) -> bool:
        """Добавление новой позиции литературы"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT OR REPLACE INTO literature (name, category, stock, min_stock, price) VALUES (?, ?, 0, ?, ?)',
                    (name, category, min_stock, price)
                )
                await db.commit()
                logger.info(f"Добавлена позиция: {name}")
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления позиции: {e}")
            return False
    
    async def update_stock(self, name: str, count: int) -> bool:
        """Обновление остатка"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'UPDATE literature SET stock = ? WHERE name = ?',
                    (count, name)
                )
                await db.commit()
                logger.info(f"Остаток по {name} обновлён: {count} шт.")
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления остатка: {e}")
            return False
    
    async def sell_item(self, name: str, qty: int) -> Tuple[bool, str]:
        """Продажа товара"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Получаем текущий остаток
                async with db.execute(
                    'SELECT stock, price FROM literature WHERE name = ?', (name,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return False, "Позиция не найдена"
                    
                    current_stock, price = row
                    if current_stock < qty:
                        return False, f"Недостаточно товара. Доступно: {current_stock} шт."
                    
                    # Обновляем остаток и количество проданного
                    new_stock = current_stock - qty
                    await db.execute(
                        'UPDATE literature SET stock = ?, sold = sold + ? WHERE name = ?',
                        (new_stock, qty, name)
                    )
                    await db.commit()
                    
                    total_price = price * qty
                    message = f"Продано: {name} ×{qty} — осталось {new_stock} шт., сумма {total_price:.0f} руб."
                    logger.info(f"💸 {message}")
                    return True, message
        except Exception as e:
            logger.error(f"Ошибка продажи товара: {e}")
            return False, f"Ошибка: {e}"
    
    async def get_stock_report(self) -> List[Dict]:
        """Получение отчёта по остаткам"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT name, stock, min_stock, sold, price FROM literature ORDER BY name'
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {
                            'name': row[0],
                            'stock': row[1],
                            'min_stock': row[2],
                            'sold': row[3],
                            'price': row[4]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Ошибка получения отчёта: {e}")
            return []
    
    async def get_low_stock(self) -> List[Dict]:
        """Получение позиций с низким остатком"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT name, stock, min_stock FROM literature WHERE stock <= min_stock ORDER BY name'
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {
                            'name': row[0],
                            'stock': row[1],
                            'min_stock': row[2]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Ошибка получения низких остатков: {e}")
            return []
    
    async def get_price_list(self) -> List[Dict]:
        """Получение прайс-листа"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT name, price FROM literature WHERE stock > 0 ORDER BY name'
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {
                            'name': row[0],
                            'price': row[1]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Ошибка получения прайса: {e}")
            return []
    
    async def get_all_items(self) -> List[str]:
        """Получение списка всех позиций для inline-кнопок"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT name FROM literature WHERE stock > 0 ORDER BY name'
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения списка позиций: {e}")
            return []
    
    async def reset_sales(self) -> bool:
        """Обнуление продаж"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('UPDATE literature SET sold = 0')
                await db.commit()
                logger.info("Продажи обнулены")
                return True
        except Exception as e:
            logger.error(f"Ошибка обнуления продаж: {e}")
            return False

# Глобальный экземпляр базы данных
db = Database()
