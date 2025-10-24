import logging
import asyncio
from typing import List, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Настройка логирования
def setup_logging():
    """Настройка логирования в консоль и файл"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def format_stock_report(report_data: List[Dict]) -> str:
    """Форматирование отчёта по остаткам"""
    if not report_data:
        return "📚 Отчёт по литературе:\nНет данных"
    
    total_sales = 0
    report_lines = ["📚 Отчёт по литературе:"]
    
    # Ограничиваем количество товаров для одного сообщения
    max_items = 20
    items_to_show = report_data[:max_items]
    
    for item in items_to_show:
        name = item['name']
        stock = item['stock']
        min_stock = item['min_stock']
        sold = item['sold']
        price = item['price']
        
        # Проверка на низкий остаток
        warning = " ⚠️" if stock <= min_stock else ""
        
        # Сокращаем длинные названия
        display_name = name[:30] + "..." if len(name) > 30 else name
        report_lines.append(f"{display_name} — {stock}/{min_stock}{warning}")
        total_sales += sold * price
    
    # Если товаров больше лимита, показываем общее количество
    if len(report_data) > max_items:
        report_lines.append(f"\n... и ещё {len(report_data) - max_items} позиций")
    
    report_lines.append(f"\nОбщая сумма продаж: {total_sales:.0f} zł")
    return "\n".join(report_lines)

def format_price_list(price_data: List[Dict]) -> str:
    """Форматирование прайс-листа"""
    if not price_data:
        return "💰 Прайс-лист:\nНет доступных позиций"
    
    price_lines = ["💰 Прайс-лист:"]
    
    # Ограничиваем количество товаров для одного сообщения
    max_items = 25
    items_to_show = price_data[:max_items]
    
    for item in items_to_show:
        name = item['name']
        price = item['price']
        
        # Сокращаем длинные названия
        display_name = name[:25] + "..." if len(name) > 25 else name
        price_lines.append(f"{display_name} — {price:.0f} zł")
    
    # Если товаров больше лимита, показываем общее количество
    if len(price_data) > max_items:
        price_lines.append(f"\n... и ещё {len(price_data) - max_items} позиций")
    
    return "\n".join(price_lines)

def format_low_stock(low_stock_data: List[Dict]) -> str:
    """Форматирование списка низких остатков"""
    if not low_stock_data:
        return "✅ Все остатки в норме"
    
    warning_lines = ["⚠️ Позиции ниже минимума:"]
    for item in low_stock_data:
        warning_lines.append(f"{item['name']} — {item['stock']}/{item['min_stock']}")
    
    return "\n".join(warning_lines)

def create_items_keyboard(items: list, action: str = "sell", show_categories: bool = False) -> InlineKeyboardMarkup:
    """Создание inline-клавиатуры с позициями для различных действий"""
    keyboard = []

    # Если показываем категории, группируем по категориям
    if show_categories:
        # Получаем уникальные категории
        categories = {}
        for item in items:
            if isinstance(item, dict):
                category = item.get('category', 'Другие')
                if category not in categories:
                    categories[category] = []
                categories[category].append(item)

        # Добавляем кнопки категорий
        for category in sorted(categories.keys()):
            keyboard.append([InlineKeyboardButton(
                text=f"📂 {category}",
                callback_data=f"category_{category}"
            )])

        # Добавляем кнопку "Все товары"
        keyboard.append([InlineKeyboardButton(
            text="📚 Все товары",
            callback_data="category_all"
        )])
    else:
        # Обычный список товаров
        # Разбиваем на строки по 2 кнопки
        for i in range(0, len(items), 2):
            row = []
            for j in range(2):
                if i + j < len(items):
                    item = items[i + j]

                    # Если item - это словарь, берем название
                    if isinstance(item, dict):
                        item_name = item['name']
                        item_id = item['id']
                    else:
                        item_name = item
                        item_id = None

                    # Ограничиваем длину названия для кнопки
                    button_text = item_name[:20] + "..." if len(item_name) > 20 else item_name

                    # Формируем callback_data в зависимости от действия
                    if action == "sell":
                        callback_data = f"sell_{item_id}"
                    elif action == "arrival":
                        callback_data = f"arrival_{item_id}"
                    elif action == "edit_item":
                        callback_data = f"edit_item_{item_id}"
                    elif action == "delete_item":
                        callback_data = f"delete_item_{item_id}"
                    elif action == "change_price":
                        callback_data = f"change_price_{item_id}"
                    elif action == "change_name":
                        callback_data = f"change_name_{item_id}"
                    else:
                        callback_data = f"sell_{item_id}"

                    row.append(InlineKeyboardButton(
                        text=button_text,
                        callback_data=callback_data
                    ))
            keyboard.append(row)

    # Добавляем кнопку отмены
    cancel_callback = "cancel_sell" if action == "sell" else "cancel_delete"
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_callback)])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_category_keyboard(items: list, category: str, action: str = "sell") -> InlineKeyboardMarkup:
    """Создание клавиатуры с товарами из определенной категории"""
    keyboard = []

    # Фильтруем товары по категории
    category_items = [item for item in items if item.get('category') == category]

    # Добавляем товары из категории
    for i in range(0, len(category_items), 2):
        row = []
        for j in range(2):
            if i + j < len(category_items):
                item = category_items[i + j]
                item_name = item['name']
                item_id = item['id']

                button_text = item_name[:20] + "..." if len(item_name) > 20 else item_name

                if action == "sell":
                    callback_data = f"sell_{item_id}"
                else:
                    callback_data = f"sell_{item_id}"

                row.append(InlineKeyboardButton(
                    text=button_text,
                    callback_data=callback_data
                ))
        keyboard.append(row)

    # Добавляем кнопки навигации
    keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data="back_to_categories"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_quantity_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры для выбора количества"""
    keyboard = [
        [
            InlineKeyboardButton(text="1", callback_data="qty_1"),
            InlineKeyboardButton(text="2", callback_data="qty_2"),
            InlineKeyboardButton(text="3", callback_data="qty_3")
        ],
        [
            InlineKeyboardButton(text="5", callback_data="qty_5"),
            InlineKeyboardButton(text="10", callback_data="qty_10"),
            InlineKeyboardButton(text="Другое", callback_data="qty_custom")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def format_demand_analytics(analytics_data: List[Dict], current_period: str, previous_period: str) -> str:
    """Форматирование отчета по аналитике спроса"""
    if not analytics_data:
        return "📊 Аналитика спроса:\nНет данных для сравнения"
    
    text = f"📊 Аналитика спроса ({current_period} vs {previous_period}):\n\n"
    
    total_current = 0
    total_previous = 0
    total_revenue_current = 0
    total_revenue_previous = 0
    
    for item in analytics_data:
        name = item['name']
        current_sold = item['current_sold']
        previous_sold = item['previous_sold']
        demand_change = item['demand_change']
        current_revenue = item['current_revenue']
        previous_revenue = item['previous_revenue']
        revenue_change = item['revenue_change']
        
        total_current += current_sold
        total_previous += previous_sold
        total_revenue_current += current_revenue
        total_revenue_previous += previous_revenue
        
        # Определяем тренд
        if demand_change > 0:
            trend = f"📈 +{demand_change}"
        elif demand_change < 0:
            trend = f"📉 {demand_change}"
        else:
            trend = "➡️ 0"
        
        text += f"📚 {name}:\n"
        text += f"   {current_period}: {current_sold} шт. ({current_revenue:.0f} zł)\n"
        text += f"   {previous_period}: {previous_sold} шт. ({previous_revenue:.0f} zł)\n"
        text += f"   Изменение: {trend}\n\n"
    
    # Общая статистика
    total_change = total_current - total_previous
    total_revenue_change = total_revenue_current - total_revenue_previous
    
    if total_change > 0:
        total_trend = f"📈 +{total_change}"
    elif total_change < 0:
        total_trend = f"📉 {total_change}"
    else:
        total_trend = "➡️ 0"
    
    text += f"📊 ИТОГО:\n"
    text += f"   Продажи: {total_current} → {total_previous} ({total_trend})\n"
    text += f"   Выручка: {total_revenue_current:.0f} → {total_revenue_previous:.0f} zł ({total_revenue_change:+.0f})\n"
    
    return text

def format_profit_report(profit_data: Dict) -> str:
    """Форматирование отчета по прибыли"""
    text = "💰 Отчет по прибыли:\n\n"
    text += f"📈 Общая выручка: {profit_data['total_revenue']:.0f} zł\n"
    text += f"💸 Общие затраты: {profit_data['total_cost']:.0f} zł\n"
    text += f"💎 Чистая прибыль: {profit_data['total_profit']:.0f} zł\n"
    text += f"📊 Маржа прибыли: {profit_data['profit_margin']:.1f}%\n"
    
    return text

async def keep_alive():
    """Функция для поддержания работы бота на Render.com"""
    while True:
        await asyncio.sleep(60)

def create_main_keyboard(role: str) -> ReplyKeyboardMarkup:
    """Создание главной клавиатуры в зависимости от роли"""
    if role == "new_user":
        keyboard = [
            [KeyboardButton(text="👑 Стать администратором")],
            [KeyboardButton(text="📚 Прайс-лист"), KeyboardButton(text="📊 Остатки")]
        ]
    elif role == "admin":
        keyboard = [
            [KeyboardButton(text="📚 Прайс-лист"), KeyboardButton(text="📊 Остатки")],
            [KeyboardButton(text="💰 Продажа"), KeyboardButton(text="📦 Приход")],
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="📈 Отчёты")],
            [KeyboardButton(text="⚙️ Управление"), KeyboardButton(text="❓ Помощь")]
        ]
    elif role == "leader":
        keyboard = [
            [KeyboardButton(text="📚 Прайс-лист"), KeyboardButton(text="📊 Остатки")],
            [KeyboardButton(text="💰 Продажа"), KeyboardButton(text="❓ Помощь")]
        ]
    else:
        keyboard = []
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=False)

def create_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Создание админского меню"""
    keyboard = [
        [InlineKeyboardButton(text="📊 Отчёты", callback_data="admin_reports")],
        [InlineKeyboardButton(text="📈 Аналитика", callback_data="admin_analytics")],
        [InlineKeyboardButton(text="💰 Прибыль", callback_data="admin_profit")],
        [InlineKeyboardButton(text="⚠️ Низкие остатки", callback_data="admin_low_stock")],
        [InlineKeyboardButton(text="📦 Управление товаром", callback_data="admin_management")],
        [InlineKeyboardButton(text="🔄 Обнулить продажи", callback_data="admin_reset_sales")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_leader_menu_keyboard() -> InlineKeyboardMarkup:
    """Создание меню для ведущего"""
    keyboard = [
        [InlineKeyboardButton(text="💰 Прайс-лист", callback_data="leader_price")],
        [InlineKeyboardButton(text="📦 Продать товар", callback_data="leader_sell")],
        [InlineKeyboardButton(text="📊 Остатки", callback_data="leader_stock")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="leader_help")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_management_menu_keyboard() -> InlineKeyboardMarkup:
    """Создание меню управления товарами для админа"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="manage_add_item")],
        [InlineKeyboardButton(text="📦 Приход товара", callback_data="manage_arrival")],
        [InlineKeyboardButton(text="📝 Редактировать товар", callback_data="manage_edit_item")],
        [InlineKeyboardButton(text="💰 Изменить цену", callback_data="manage_change_price")],
        [InlineKeyboardButton(text="📋 Изменить название", callback_data="manage_change_name")],
        [InlineKeyboardButton(text="🗑️ Удалить товар", callback_data="manage_delete_item")],
        [InlineKeyboardButton(text="🔄 Обновить остатки", callback_data="manage_update_stock")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_reports_menu_keyboard() -> InlineKeyboardMarkup:
    """Создание меню отчётов для админа"""
    keyboard = [
        [InlineKeyboardButton(text="📊 Отчёт по остаткам", callback_data="reports_stock")],
        [InlineKeyboardButton(text="📋 Полная инвентаризация", callback_data="reports_inventory")],
        [InlineKeyboardButton(text="⚠️ Низкие остатки", callback_data="reports_low_stock")],
        [InlineKeyboardButton(text="📈 Аналитика спроса", callback_data="reports_analytics")],
        [InlineKeyboardButton(text="💰 Отчёт по прибыли", callback_data="reports_profit")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_reports_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры отчётов"""
    keyboard = [
        [InlineKeyboardButton(text="📊 Полный отчёт", callback_data="report_full")],
        [InlineKeyboardButton(text="📈 Инвентаризация", callback_data="report_inventory")],
        [InlineKeyboardButton(text="📉 Низкие остатки", callback_data="report_low_stock")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_management_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры управления"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="add_item")],
        [InlineKeyboardButton(text="📦 Приход товара", callback_data="arrival")],
        [InlineKeyboardButton(text="📝 Обновить остаток", callback_data="update_stock")],
        [InlineKeyboardButton(text="👥 Добавить ведущего", callback_data="add_leader")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """Создание клавиатуры подтверждения"""
    keyboard = [
        [InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
