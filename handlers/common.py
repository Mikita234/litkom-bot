import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Используем ту же базу данных, что и в main.py
import os
try:
    from db_postgres import db
except ImportError:
    from db import db
from utils import format_price_list, create_items_keyboard, create_quantity_keyboard, create_main_keyboard, create_admin_menu_keyboard, create_reports_keyboard, create_management_keyboard

logger = logging.getLogger(__name__)
router = Router()

# Состояния для FSM
class SellStates(StatesGroup):
    waiting_for_item = State()
    waiting_for_quantity = State()

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    logger.info(f"Получена команда /start от пользователя {message.from_user.id}")
    
    user_id = message.from_user.id
    role = await db.get_user_role(user_id)
    logger.info(f"Роль пользователя {user_id}: {role}")
    
    # Если команда вызвана в группе, проверяем права администратора
    if message.chat.type in ['group', 'supergroup']:
        try:
            chat_member = await message.bot.get_chat_member(message.chat.id, user_id)
            if chat_member.status in ['creator', 'administrator'] and not role:
                # Автоматически добавляем администраторов группы как ведущих
                await db.add_user(user_id, "leader", message.from_user.full_name)
                role = "leader"
        except Exception:
            pass
    
    if not role:
        text = (
            "👋 Добро пожаловать в бот Литературного Комитета АН!\n\n"
            "Для начала работы введите команду /set_admin, чтобы назначить себя администратором."
        )
    elif role == "admin":
        text = (
            "👑 Вы администратор бота.\n\n"
            "Доступные команды:\n"
            "/add_leader - добавить ведущего\n"
            "/add_item - добавить позицию\n"
            "/update_stock - обновить остаток\n"
            "/report - отчёт по остаткам\n"
            "/inventory - полная инвентаризация\n"
            "/low - низкие остатки\n"
            "/reset_sales - обнулить продажи\n"
            "/price - прайс-лист\n"
            "/sell - продажа\n"
            "/stock - остатки\n"
            "/help - справка"
        )
    elif role == "leader":
        text = (
            "📚 Вы ведущий бота.\n\n"
            "Доступные команды:\n"
            "/price - прайс-лист\n"
            "/sell - продажа\n"
            "/stock - остатки\n"
            "/help - справка"
        )
    else:
        text = "❌ У вас нет доступа к боту. Обратитесь к администратору."
    
    await message.answer(text)
    logger.info(f"Отправлен ответ пользователю {user_id}: {text[:50]}...")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    user_id = message.from_user.id
    role = await db.get_user_role(user_id)
    
    if role == "admin":
        text = (
            "👑 Справка для администратора:\n\n"
            "📋 Управление пользователями:\n"
            "• /add_leader - добавить ведущего\n\n"
            "📚 Управление литературой:\n"
            "• /add_item - добавить новую позицию\n"
            "• /update_stock - обновить остаток\n"
            "• /report - полный отчёт по остаткам\n"
            "• /inventory - полная инвентаризация\n"
            "• /low - позиции ниже минимума\n"
            "• /reset_sales - обнулить продажи (новый месяц)\n\n"
            "📊 Аналитика и финансы:\n"
            "• /analytics - аналитика спроса (прирост/отток)\n"
            "• /profit - отчёт по прибыли\n\n"
            "💰 Работа с продажами:\n"
            "• /price - прайс-лист\n"
            "• /sell - отметить продажу\n"
            "• /stock - текущие остатки"
        )
    elif role == "leader":
        text = (
            "📚 Справка для ведущего:\n\n"
            "💰 Доступные команды:\n"
            "• /price - показать прайс-лист\n"
            "• /sell - отметить продажу\n"
            "• /stock - показать текущие остатки\n\n"
            "💡 Для продажи используйте /sell, выберите позицию и количество."
        )
    else:
        text = "❌ У вас нет доступа к боту."
    
    await message.answer(text)

@router.message(Command("price"))
async def cmd_price(message: Message):
    """Обработчик команды /price"""
    user_id = message.from_user.id
    role = await db.get_user_role(user_id)
    
    if role not in ['admin', 'leader']:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    price_data = await db.get_price_list()
    text = format_price_list(price_data)
    await message.answer(text)

@router.message(Command("stock"))
async def cmd_stock(message: Message):
    """Обработчик команды /stock"""
    user_id = message.from_user.id
    role = await db.get_user_role(user_id)
    
    if role not in ['admin', 'leader']:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    report_data = await db.get_stock_report()
    if not report_data:
        await message.answer("📚 Нет данных об остатках.")
        return
    
    text = "📚 Текущие остатки:\n\n"
    for item in report_data:
        name = item['name']
        stock = item['stock']
        min_stock = item['min_stock']
        warning = " ⚠️" if stock <= min_stock else ""
        text += f"{name} — {stock}/{min_stock}{warning}\n"
    
    await message.answer(text)

@router.message(Command("sell"))
async def cmd_sell(message: Message, state: FSMContext):
    """Обработчик команды /sell"""
    user_id = message.from_user.id
    role = await db.get_user_role(user_id)
    
    if role not in ['admin', 'leader']:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    items = await db.get_all_items()
    if not items:
        await message.answer("❌ Нет доступных позиций для продажи.")
        return
    
    keyboard = create_items_keyboard(items, "sell")
    await message.answer(
        "💰 Выберите позицию для продажи:",
        reply_markup=keyboard
    )
    await state.set_state(SellStates.waiting_for_item)

@router.callback_query(F.data.startswith("sell_"))
async def process_item_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора позиции для продажи"""
    await callback.answer()
    
    item_name = callback.data[5:]  # Убираем "sell_"
    await state.update_data(selected_item=item_name)
    
    keyboard = create_quantity_keyboard()
    await callback.message.edit_text(
        f"📦 Выбрано: {item_name}\n\nВыберите количество:",
        reply_markup=keyboard
    )
    await state.set_state(SellStates.waiting_for_quantity)

@router.callback_query(F.data.startswith("qty_"))
async def process_quantity_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора количества"""
    await callback.answer()
    
    data = await state.get_data()
    item_name = data.get('selected_item')
    
    if callback.data == "qty_custom":
        await callback.message.edit_text(
            f"📦 {item_name}\n\nВведите количество вручную:"
        )
        return
    
    try:
        quantity = int(callback.data[4:])  # Убираем "qty_"
        await process_sale(callback, state, item_name, quantity)
    except ValueError:
        await callback.message.edit_text("❌ Ошибка в количестве.")

@router.message(SellStates.waiting_for_quantity)
async def process_custom_quantity(message: Message, state: FSMContext):
    """Обработка ввода количества вручную"""
    try:
        quantity = int(message.text)
        if quantity <= 0:
            await message.answer("❌ Количество должно быть больше 0.")
            return
        
        data = await state.get_data()
        item_name = data.get('selected_item')
        
        # Создаем fake callback для обработки продажи
        class FakeCallback:
            def __init__(self, message):
                self.message = message
                self.data = ""
            
            async def answer(self):
                pass
        
        fake_callback = FakeCallback(message)
        await process_sale(fake_callback, state, item_name, quantity)
        
    except ValueError:
        await message.answer("❌ Введите корректное число.")
    except Exception as e:
        logger.error(f"Ошибка обработки количества: {e}")
        await message.answer("❌ Произошла ошибка.")

async def process_sale(callback, state: FSMContext, item_name: str, quantity: int):
    """Обработка продажи"""
    success, message_text = await db.sell_item(item_name, quantity)
    
    if success:
        # Проверяем, не стал ли остаток ниже минимума
        report_data = await db.get_stock_report()
        for item in report_data:
            if item['name'] == item_name and item['stock'] <= item['min_stock']:
                message_text += f"\n\n⚠️ Остаток {item_name} ниже минимума ({item['stock']}/{item['min_stock']})."
                break
        
        if hasattr(callback, 'message') and hasattr(callback.message, 'edit_text'):
            await callback.message.edit_text(f"✅ {message_text}")
        else:
            await callback.message.answer(f"✅ {message_text}")
    else:
        if hasattr(callback, 'message') and hasattr(callback.message, 'edit_text'):
            await callback.message.edit_text(f"❌ {message_text}")
        else:
            await callback.message.answer(f"❌ {message_text}")
    
    await state.clear()

@router.callback_query(F.data == "cancel_sell")
async def cancel_sell(callback: CallbackQuery, state: FSMContext):
    """Отмена продажи"""
    await callback.answer()
    await callback.message.edit_text("❌ Продажа отменена.")
    await state.clear()

# Обработчики кнопок
@router.message(lambda message: message.text == "👑 Стать администратором")
async def handle_become_admin(message: Message):
    """Обработка кнопки 'Стать администратором'"""
    user_id = message.from_user.id
    role = await db.get_user_role(user_id)
    
    if role is None:
        # Добавляем пользователя как администратора
        success = await db.add_user(user_id, "admin", message.from_user.full_name)
        if success:
            await message.answer(
                "✅ Вы назначены администратором!\n\n"
                "Теперь у вас есть доступ ко всем функциям бота.",
                reply_markup=create_main_keyboard("admin")
            )
        else:
            await message.answer("❌ Ошибка при назначении администратором.")
    else:
        await message.answer("ℹ️ У вас уже есть роль в системе.")

@router.message(lambda message: message.text == "📚 Прайс-лист")
async def handle_price_list(message: Message):
    """Обработка кнопки 'Прайс-лист'"""
    price_data = await db.get_stock_report()
    text = format_price_list(price_data)
    await message.answer(text)

@router.message(lambda message: message.text == "📊 Остатки")
async def handle_stock(message: Message):
    """Обработка кнопки 'Остатки'"""
    report_data = await db.get_stock_report()
    if not report_data:
        await message.answer("❌ Нет данных об остатках.")
        return
    
    text = "📊 Текущие остатки:\n\n"
    for item in report_data:
        warning = " ⚠️" if item['stock'] <= item['min_stock'] else ""
        text += f"📚 {item['name']}\n"
        text += f"   Остаток: {item['stock']} шт.{warning}\n"
        text += f"   Цена: {item['price']:.0f} zł\n\n"
    
    await message.answer(text)

@router.message(lambda message: message.text == "💰 Продажа")
async def handle_sell_button(message: Message):
    """Обработка кнопки 'Продажа'"""
    user_id = message.from_user.id
    role = await db.get_user_role(user_id)
    
    if role not in ["admin", "leader"]:
        await message.answer("❌ У вас нет прав для продажи товаров.")
        return
    
    # Получаем список товаров для продажи
    items = await db.get_all_items()
    if not items:
        await message.answer("❌ Нет товаров для продажи.")
        return
    
    keyboard = create_items_keyboard(items, "sell")
    await message.answer(
        "💰 <b>Продажа товара</b>\n\n"
        "Выберите товар для продажи:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(lambda message: message.text == "📈 Отчёты")
async def handle_reports_button(message: Message):
    """Обработка кнопки 'Отчёты' (только для админов)"""
    user_id = message.from_user.id
    role = await db.get_user_role(user_id)
    
    if role != "admin":
        await message.answer("❌ Только администратор может просматривать отчёты.")
        return
    
    keyboard = create_reports_keyboard()
    await message.answer(
        "📊 <b>Отчёты и аналитика</b>\n\n"
        "Выберите тип отчёта:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(lambda message: message.text == "⚙️ Управление")
async def handle_management_button(message: Message):
    """Обработка кнопки 'Управление' (только для админов)"""
    user_id = message.from_user.id
    role = await db.get_user_role(user_id)
    
    if role != "admin":
        await message.answer("❌ Только администратор может управлять системой.")
        return
    
    keyboard = create_management_keyboard()
    await message.answer(
        "⚙️ <b>Управление системой</b>\n\n"
        "Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(lambda message: message.text == "❓ Помощь")
async def handle_help_button(message: Message):
    """Обработка кнопки 'Помощь'"""
    user_id = message.from_user.id
    role = await db.get_user_role(user_id)
    
    if role == "admin":
        text = (
            "👑 <b>Справка для администратора</b>\n\n"
            "Доступные команды:\n"
            "• /add_item - добавить товар\n"
            "• /update_stock - обновить остаток\n"
            "• /arrival - приход товара\n"
            "• /report - полный отчёт\n"
            "• /inventory - инвентаризация\n"
            "• /analytics - аналитика спроса\n"
            "• /profit - отчёт по прибыли\n"
            "• /low - низкие остатки\n"
            "• /reset_sales - обнулить продажи\n"
            "• /add_leader - добавить ведущего\n\n"
            "Используйте кнопки для быстрого доступа к функциям!"
        )
    elif role == "leader":
        text = (
            "📚 <b>Справка для ведущего</b>\n\n"
            "Доступные команды:\n"
            "• /price - прайс-лист\n"
            "• /sell - продажа товара\n"
            "• /stock - остатки\n\n"
            "Используйте кнопки для быстрого доступа к функциям!"
        )
    else:
        text = (
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Этот бот поможет управлять литературой АН.\n"
            "Нажмите '👑 Стать администратором' для начала работы."
        )
    
    await message.answer(text, parse_mode="HTML")
