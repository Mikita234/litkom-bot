import logging
import asyncpg
import os
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL не найден в переменных окружения")
    
    async def get_connection(self):
        """Получение подключения к PostgreSQL"""
        return await asyncpg.connect(self.db_url)
    
    async def init_database(self):
        """Инициализация базы данных"""
        try:
            conn = await self.get_connection()
            
            # Создаем таблицы
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
            
            await conn.close()
            logger.info("База данных PostgreSQL инициализирована успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            return False
    
    async def add_user(self, tg_id: int, role: str, name: str) -> bool:
        """Добавление пользователя"""
        try:
            conn = await self.get_connection()
            await conn.execute(
                'INSERT INTO users (tg_id, role, name) VALUES ($1, $2, $3) ON CONFLICT (tg_id) DO UPDATE SET role = $2, name = $3',
                tg_id, role, name
            )
            await conn.close()
            logger.info(f"Пользователь {tg_id} добавлен с ролью {role}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False
    
    async def get_user_role(self, tg_id: int) -> Optional[str]:
        """Получение роли пользователя"""
        try:
            conn = await self.get_connection()
            role = await conn.fetchval('SELECT role FROM users WHERE tg_id = $1', tg_id)
            await conn.close()
            return role
        except Exception as e:
            logger.error(f"Ошибка получения роли пользователя: {e}")
            return None
    
    async def is_admin(self, tg_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        role = await self.get_user_role(tg_id)
        return role == "admin"
    
    async def add_item(self, name: str, category: str, price: float, cost: float, min_stock: int) -> bool:
        """Добавление новой позиции литературы"""
        try:
            conn = await self.get_connection()
            await conn.execute(
                'INSERT INTO literature (name, category, stock, min_stock, price, cost) VALUES ($1, $2, 0, $3, $4, $5) ON CONFLICT (name) DO NOTHING',
                name, category, min_stock, price, cost
            )
            await conn.close()
            logger.info(f"Добавлена позиция: {name} (цена: {price}, себестоимость: {cost})")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления позиции: {e}")
            return False
    
    async def update_stock(self, name: str, new_stock: int) -> bool:
        """Обновление остатка товара"""
        try:
            conn = await self.get_connection()
            result = await conn.execute(
                'UPDATE literature SET stock = $1 WHERE name = $2',
                new_stock, name
            )
            await conn.close()
            
            if result == "UPDATE 1":
                logger.info(f"Остаток {name} обновлен: {new_stock} шт.")
                return True
            else:
                logger.warning(f"Товар {name} не найден")
                return False
        except Exception as e:
            logger.error(f"Ошибка обновления остатка: {e}")
            return False
    
    async def sell_item(self, name: str, quantity: int) -> bool:
        """Продажа товара"""
        try:
            conn = await self.get_connection()
            
            # Получаем текущий остаток
            current_stock = await conn.fetchval('SELECT stock FROM literature WHERE name = $1', name)
            if current_stock is None:
                await conn.close()
                return False
            
            if current_stock < quantity:
                await conn.close()
                return False
            
            # Обновляем остаток и продажи
            new_stock = current_stock - quantity
            await conn.execute(
                'UPDATE literature SET stock = $1, sold = sold + $2 WHERE name = $3',
                new_stock, quantity, name
            )
            
            await conn.close()
            logger.info(f"Продано {quantity} шт. {name}, остаток: {new_stock}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка продажи: {e}")
            return False
    
    async def get_stock_report(self) -> List[Dict[str, Any]]:
        """Получение отчета по остаткам"""
        try:
            conn = await self.get_connection()
            rows = await conn.fetch('''
                SELECT name, stock, min_stock, price, sold 
                FROM literature 
                ORDER BY category, name
            ''')
            await conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения отчета: {e}")
            return []
    
    async def get_low_stock(self) -> List[Dict[str, Any]]:
        """Получение товаров с низким остатком"""
        try:
            conn = await self.get_connection()
            rows = await conn.fetch('''
                SELECT name, stock, min_stock 
                FROM literature 
                WHERE stock <= min_stock
                ORDER BY stock ASC
            ''')
            await conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения низких остатков: {e}")
            return []
    
    async def reset_sales(self) -> bool:
        """Обнуление продаж"""
        try:
            conn = await self.get_connection()
            await conn.execute('UPDATE literature SET sold = 0')
            await conn.close()
            logger.info("Продажи обнулены")
            return True
        except Exception as e:
            logger.error(f"Ошибка обнуления продаж: {e}")
            return False
    
    async def get_all_items(self) -> List[Dict[str, Any]]:
        """Получение всех товаров"""
        try:
            conn = await self.get_connection()
            rows = await conn.fetch('SELECT id, name, stock, price FROM literature ORDER BY name')
            await conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения товаров: {e}")
            return []
    
    async def get_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Получение товара по ID"""
        try:
            conn = await self.get_connection()
            row = await conn.fetchrow(
                'SELECT id, name, category, stock, min_stock, price, cost, sold FROM literature WHERE id = $1',
                item_id
            )
            await conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения товара по ID: {e}")
            return None

# Глобальный экземпляр базы данных
db = Database()
