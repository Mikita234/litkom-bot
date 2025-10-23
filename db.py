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
                        cost REAL NOT NULL DEFAULT 0.0,
                        sold INTEGER NOT NULL DEFAULT 0
                    )
                ''')
                
                # Создание таблицы для ежемесячных продаж (аналитика)
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS monthly_sales (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    
    async def add_item(self, name: str, category: str, price: float, cost: float, min_stock: int) -> bool:
        """Добавление новой позиции литературы"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT OR REPLACE INTO literature (name, category, stock, min_stock, price, cost) VALUES (?, ?, 0, ?, ?, ?)',
                    (name, category, min_stock, price, cost)
                )
                await db.commit()
                logger.info(f"Добавлена позиция: {name} (цена: {price}, себестоимость: {cost})")
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
                    message = f"Продано: {name} ×{qty} — осталось {new_stock} шт., сумма {total_price:.0f} zł"
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
        """Обнуление продаж с сохранением в аналитику"""
        try:
            import datetime
            current_date = datetime.date.today()
            year = current_date.year
            month = current_date.month
            
            async with aiosqlite.connect(self.db_path) as db:
                # Получаем текущие продажи для сохранения в аналитику
                cursor = await db.execute(
                    'SELECT id, sold, price, cost FROM literature WHERE sold > 0'
                )
                items = await cursor.fetchall()
                
                for item_id, sold_qty, price, cost in items:
                    total_revenue = sold_qty * price
                    total_cost = sold_qty * cost
                    
                    # Сохраняем в monthly_sales
                    await db.execute(
                        '''INSERT OR REPLACE INTO monthly_sales 
                           (item_id, year, month, sold_quantity, total_revenue, total_cost) 
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (item_id, year, month, sold_qty, total_revenue, total_cost)
                    )
                
                # Обнуляем продажи
                await db.execute('UPDATE literature SET sold = 0')
                await db.commit()
                logger.info(f"Продажи обнулены и сохранены в аналитику за {month}.{year}")
                return True
        except Exception as e:
            logger.error(f"Ошибка обнуления продаж: {e}")
            return False
    
    async def get_demand_analytics(self, current_year: int, current_month: int, 
                                 prev_year: int, prev_month: int) -> List[Dict]:
        """Получение аналитики спроса за два периода"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                query = '''
                    SELECT 
                        l.name,
                        COALESCE(curr.sold_quantity, 0) as current_sold,
                        COALESCE(prev.sold_quantity, 0) as previous_sold,
                        COALESCE(curr.total_revenue, 0) as current_revenue,
                        COALESCE(prev.total_revenue, 0) as previous_revenue,
                        COALESCE(curr.total_cost, 0) as current_cost,
                        COALESCE(prev.total_cost, 0) as previous_cost
                    FROM literature l
                    LEFT JOIN monthly_sales curr ON l.id = curr.item_id 
                        AND curr.year = ? AND curr.month = ?
                    LEFT JOIN monthly_sales prev ON l.id = prev.item_id 
                        AND prev.year = ? AND prev.month = ?
                    WHERE COALESCE(curr.sold_quantity, 0) > 0 OR COALESCE(prev.sold_quantity, 0) > 0
                    ORDER BY l.name
                '''
                cursor = await db.execute(query, (current_year, current_month, prev_year, prev_month))
                rows = await cursor.fetchall()
                
                analytics = []
                for row in rows:
                    current_sold, previous_sold = row[1], row[2]
                    current_revenue, previous_revenue = row[3], row[4]
                    current_cost, previous_cost = row[5], row[6]
                    
                    # Вычисляем прирост/отток
                    demand_change = current_sold - previous_sold
                    revenue_change = current_revenue - previous_revenue
                    profit_change = (current_revenue - current_cost) - (previous_revenue - previous_cost)
                    
                    analytics.append({
                        'name': row[0],
                        'current_sold': current_sold,
                        'previous_sold': previous_sold,
                        'demand_change': demand_change,
                        'current_revenue': current_revenue,
                        'previous_revenue': previous_revenue,
                        'revenue_change': revenue_change,
                        'current_profit': current_revenue - current_cost,
                        'previous_profit': previous_revenue - previous_cost,
                        'profit_change': profit_change
                    })
                
                return analytics
        except Exception as e:
            logger.error(f"Ошибка получения аналитики спроса: {e}")
            return []
    
    async def get_profit_report(self) -> Dict:
        """Получение отчета по прибыли"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    '''SELECT 
                        SUM(sold * price) as total_revenue,
                        SUM(sold * cost) as total_cost,
                        SUM(sold * (price - cost)) as total_profit
                       FROM literature'''
                )
                row = await cursor.fetchone()
                
                if row:
                    return {
                        'total_revenue': row[0] or 0,
                        'total_cost': row[1] or 0,
                        'total_profit': row[2] or 0,
                        'profit_margin': ((row[2] or 0) / (row[0] or 1)) * 100 if row[0] else 0
                    }
                return {'total_revenue': 0, 'total_cost': 0, 'total_profit': 0, 'profit_margin': 0}
        except Exception as e:
            logger.error(f"Ошибка получения отчета по прибыли: {e}")
            return {'total_revenue': 0, 'total_cost': 0, 'total_profit': 0, 'profit_margin': 0}

    async def get_item_by_id(self, item_id: int) -> dict:
        """Получение товара по ID"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT id, name, category, stock, min_stock, price, cost, sold FROM literature WHERE id = ?',
                    (item_id,)
                )
                row = await cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'name': row[1],
                        'category': row[2],
                        'stock': row[3],
                        'min_stock': row[4],
                        'price': row[5],
                        'cost': row[6],
                        'sold': row[7]
                    }
                return None
        except Exception as e:
            logger.error(f"Ошибка получения товара по ID: {e}")
            return None

# Глобальный экземпляр базы данных
db = Database()
