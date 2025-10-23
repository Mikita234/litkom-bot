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
    
    async def is_leader(self, tg_id: int) -> bool:
        """Проверка, является ли пользователь ведущим"""
        role = await self.get_user_role(tg_id)
        return role == "leader"
    
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
    
    async def sell_item(self, name: str, quantity: int) -> tuple[bool, str]:
        """Продажа товара"""
        try:
            conn = await self.get_connection()
            
            # Получаем текущий остаток
            current_stock = await conn.fetchval('SELECT stock FROM literature WHERE name = $1', name)
            if current_stock is None:
                await conn.close()
                return False, "Позиция не найдена"
            
            if current_stock < quantity:
                await conn.close()
                return False, f"Недостаточно товара. Доступно: {current_stock} шт."
            
            # Обновляем остаток и продажи
            new_stock = current_stock - quantity
            await conn.execute(
                'UPDATE literature SET stock = $1, sold = sold + $2 WHERE name = $3',
                new_stock, quantity, name
            )
            
            await conn.close()
            logger.info(f"Продано {quantity} шт. {name}, остаток: {new_stock}")
            return True, f"Продано: {name} ×{quantity} — осталось {new_stock} шт."
            
        except Exception as e:
            logger.error(f"Ошибка продажи: {e}")
            return False, f"Ошибка продажи: {e}"
    
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
    
    async def get_price_list(self) -> List[Dict[str, Any]]:
        """Получение прайс-листа"""
        try:
            conn = await self.get_connection()
            rows = await conn.fetch(
                'SELECT name, price FROM literature WHERE stock > 0 ORDER BY name'
            )
            await conn.close()
            return [{'name': row['name'], 'price': row['price']} for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения прайса: {e}")
            return []
    
    async def archive_monthly_sales(self) -> bool:
        """Архивирование продаж в аналитику"""
        try:
            import datetime
            current_date = datetime.date.today()
            year = current_date.year
            month = current_date.month
            
            conn = await self.get_connection()
            
            # Получаем текущие продажи для сохранения в аналитику
            items = await conn.fetch(
                'SELECT id, sold, price, cost FROM literature WHERE sold > 0'
            )
            
            for item in items:
                total_revenue = item['sold'] * item['price']
                total_cost = item['sold'] * item['cost']
                
                # Сохраняем в monthly_sales
                await conn.execute(
                    '''INSERT INTO monthly_sales 
                       (item_id, year, month, sold_quantity, total_revenue, total_cost) 
                       VALUES ($1, $2, $3, $4, $5, $6)
                       ON CONFLICT (item_id, year, month) 
                       DO UPDATE SET sold_quantity = $4, total_revenue = $5, total_cost = $6''',
                    item['id'], year, month, item['sold'], total_revenue, total_cost
                )
            
            # Обнуляем продажи
            await conn.execute('UPDATE literature SET sold = 0')
            await conn.close()
            
            logger.info(f"Продажи архивированы за {month}.{year}")
            return True
        except Exception as e:
            logger.error(f"Ошибка архивирования продаж: {e}")
            return False
    
    async def get_demand_analytics(self, current_year: int, current_month: int, 
                                 prev_year: int, prev_month: int) -> List[Dict[str, Any]]:
        """Получение аналитики спроса за два периода"""
        try:
            conn = await self.get_connection()
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
                    AND curr.year = $1 AND curr.month = $2
                LEFT JOIN monthly_sales prev ON l.id = prev.item_id 
                    AND prev.year = $3 AND prev.month = $4
                WHERE COALESCE(curr.sold_quantity, 0) > 0 OR COALESCE(prev.sold_quantity, 0) > 0
                ORDER BY l.name
            '''
            rows = await conn.fetch(query, current_year, current_month, prev_year, prev_month)
            await conn.close()
            
            analytics = []
            for row in rows:
                current_sold, previous_sold = row['current_sold'], row['previous_sold']
                current_revenue, previous_revenue = row['current_revenue'], row['previous_revenue']
                current_cost, previous_cost = row['current_cost'], row['previous_cost']
                
                # Вычисляем изменения
                demand_change = 0
                if previous_sold > 0:
                    demand_change = ((current_sold - previous_sold) / previous_sold) * 100
                
                revenue_change = 0
                if previous_revenue > 0:
                    revenue_change = ((current_revenue - previous_revenue) / previous_revenue) * 100
                
                profit_current = current_revenue - current_cost
                profit_previous = previous_revenue - previous_cost
                profit_change = 0
                if profit_previous > 0:
                    profit_change = ((profit_current - profit_previous) / profit_previous) * 100
                
                analytics.append({
                    'name': row['name'],
                    'current_sold': current_sold,
                    'previous_sold': previous_sold,
                    'demand_change': demand_change,
                    'current_revenue': current_revenue,
                    'previous_revenue': previous_revenue,
                    'revenue_change': revenue_change,
                    'current_profit': profit_current,
                    'previous_profit': profit_previous,
                    'profit_change': profit_change
                })
            
            return analytics
        except Exception as e:
            logger.error(f"Ошибка получения аналитики: {e}")
            return []
    
    async def get_profit_report(self) -> Dict[str, Any]:
        """Получение отчёта о прибыли"""
        try:
            conn = await self.get_connection()
            
            # Общая статистика
            total_stats = await conn.fetchrow('''
                SELECT 
                    SUM(sold * price) as total_revenue,
                    SUM(sold * cost) as total_cost,
                    SUM(sold * (price - cost)) as total_profit
                FROM literature
            ''')
            
            # Топ товары по прибыли
            top_items = await conn.fetch('''
                SELECT name, sold, price, cost, 
                       (sold * price) as revenue,
                       (sold * (price - cost)) as profit
                FROM literature 
                WHERE sold > 0 
                ORDER BY profit DESC 
                LIMIT 10
            ''')
            
            await conn.close()
            
            return {
                'total_revenue': total_stats['total_revenue'] or 0,
                'total_cost': total_stats['total_cost'] or 0,
                'total_profit': total_stats['total_profit'] or 0,
                'top_items': [dict(item) for item in top_items]
            }
        except Exception as e:
            logger.error(f"Ошибка получения отчёта о прибыли: {e}")
            return {
                'total_revenue': 0,
                'total_cost': 0,
                'total_profit': 0,
                'top_items': []
            }
    
    async def update_item(self, item_id: int, name: str = None, category: str = None, 
                         price: float = None, cost: float = None, min_stock: int = None) -> bool:
        """Обновление товара"""
        try:
            conn = await self.get_connection()
            
            # Строим динамический запрос
            updates = []
            params = []
            param_count = 1
            
            if name is not None:
                updates.append(f"name = ${param_count}")
                params.append(name)
                param_count += 1
            
            if category is not None:
                updates.append(f"category = ${param_count}")
                params.append(category)
                param_count += 1
            
            if price is not None:
                updates.append(f"price = ${param_count}")
                params.append(price)
                param_count += 1
            
            if cost is not None:
                updates.append(f"cost = ${param_count}")
                params.append(cost)
                param_count += 1
            
            if min_stock is not None:
                updates.append(f"min_stock = ${param_count}")
                params.append(min_stock)
                param_count += 1
            
            if not updates:
                await conn.close()
                return False
            
            # Добавляем item_id в конец
            params.append(item_id)
            
            query = f"UPDATE literature SET {', '.join(updates)} WHERE id = ${param_count}"
            await conn.execute(query, *params)
            await conn.close()
            
            logger.info(f"Товар {item_id} обновлен")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления товара: {e}")
            return False
    
    async def delete_item(self, item_id: int) -> bool:
        """Удаление товара"""
        try:
            conn = await self.get_connection()
            
            # Получаем название товара для лога
            item_name = await conn.fetchval('SELECT name FROM literature WHERE id = $1', item_id)
            
            # Удаляем товар
            await conn.execute('DELETE FROM literature WHERE id = $1', item_id)
            await conn.close()
            
            logger.info(f"Товар {item_name} (ID: {item_id}) удален")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления товара: {e}")
            return False
    
    async def get_item_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Получение товара по названию"""
        try:
            conn = await self.get_connection()
            row = await conn.fetchrow(
                'SELECT id, name, category, stock, min_stock, price, cost, sold FROM literature WHERE name = $1',
                name
            )
            await conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения товара по названию: {e}")
            return None

# Глобальный экземпляр базы данных
db = Database()
