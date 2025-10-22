import logging
import asyncio
from typing import List, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
    
    for item in report_data:
        name = item['name']
        stock = item['stock']
        min_stock = item['min_stock']
        sold = item['sold']
        price = item['price']
        
        # Проверка на низкий остаток
        warning = " ⚠️" if stock <= min_stock else ""
        
        report_lines.append(f"{name} — {stock}/{min_stock}{warning}")
        total_sales += sold * price
    
    report_lines.append(f"\nОбщая сумма продаж: {total_sales:.0f} руб.")
    return "\n".join(report_lines)

def format_price_list(price_data: List[Dict]) -> str:
    """Форматирование прайс-листа"""
    if not price_data:
        return "💰 Прайс-лист:\nНет доступных позиций"
    
    price_lines = ["💰 Прайс-лист:"]
    for item in price_data:
        price_lines.append(f"{item['name']} — {item['price']:.0f} руб.")
    
    return "\n".join(price_lines)

def format_low_stock(low_stock_data: List[Dict]) -> str:
    """Форматирование списка низких остатков"""
    if not low_stock_data:
        return "✅ Все остатки в норме"
    
    warning_lines = ["⚠️ Позиции ниже минимума:"]
    for item in low_stock_data:
        warning_lines.append(f"{item['name']} — {item['stock']}/{item['min_stock']}")
    
    return "\n".join(warning_lines)

def create_items_keyboard(items: List[str]) -> InlineKeyboardMarkup:
    """Создание inline-клавиатуры с позициями для продажи"""
    keyboard = []
    
    # Разбиваем на строки по 2 кнопки
    for i in range(0, len(items), 2):
        row = []
        for j in range(2):
            if i + j < len(items):
                item = items[i + j]
                # Ограничиваем длину названия для кнопки
                button_text = item[:20] + "..." if len(item) > 20 else item
                row.append(InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"sell_{item}"
                ))
        keyboard.append(row)
    
    # Добавляем кнопку отмены
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")])
    
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

async def keep_alive():
    """Функция для поддержания работы бота на Render.com"""
    while True:
        await asyncio.sleep(60)
