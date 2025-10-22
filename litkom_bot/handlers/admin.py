import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, ChatTypeFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import db
from utils import format_stock_report, format_low_stock

logger = logging.getLogger(__name__)
router = Router()

# Состояния для FSM
class AdminStates(StatesGroup):
    waiting_for_admin_confirmation = State()
    waiting_for_leader_id = State()
    waiting_for_item_name = State()
    waiting_for_item_category = State()
    waiting_for_item_price = State()
    waiting_for_item_min_stock = State()
    waiting_for_stock_name = State()
    waiting_for_stock_count = State()

@router.message(Command("set_admin"))
async def cmd_set_admin(message: Message, state: FSMContext):
    """Обработчик команды /set_admin"""
    user_id = message.from_user.id
    current_role = await db.get_user_role(user_id)
    
    if current_role == "admin":
        await message.answer("👑 Вы уже являетесь администратором.")
        return
    
    if current_role is None:
        # Первый пользователь становится админом
        success = await db.add_user(user_id, "admin", message.from_user.full_name)
        if success:
            await message.answer(
                "👑 Поздравляем! Вы назначены администратором бота.\n\n"
                "Теперь вы можете:\n"
                "• Добавлять ведущих командой /add_leader\n"
                "• Управлять литературой\n"
                "• Просматривать отчёты\n"
                "• Обнулять продажи"
            )
        else:
            await message.answer("❌ Ошибка при назначении администратора.")
    else:
        await message.answer("❌ У вас уже есть роль в системе.")

@router.message(Command("add_leader"))
async def cmd_add_leader(message: Message, state: FSMContext):
    """Обработчик команды /add_leader"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может добавлять ведущих.")
        return
    
    await message.answer(
        "👥 Добавление ведущего\n\n"
        "Перешлите сообщение от пользователя, которого хотите сделать ведущим, "
        "или введите его Telegram ID:"
    )
    await state.set_state(AdminStates.waiting_for_leader_id)

@router.message(AdminStates.waiting_for_leader_id)
async def process_leader_id(message: Message, state: FSMContext):
    """Обработка ID ведущего"""
    try:
        if message.forward_from:
            # Если пересланное сообщение
            leader_id = message.forward_from.id
            leader_name = message.forward_from.full_name
        else:
            # Если введен ID вручную
            leader_id = int(message.text)
            leader_name = None
        
        success = await db.add_user(leader_id, "leader", leader_name)
        if success:
            await message.answer(f"✅ Пользователь {leader_id} назначен ведущим.")
        else:
            await message.answer("❌ Ошибка при добавлении ведущего.")
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректный Telegram ID (число).")
    except Exception as e:
        logger.error(f"Ошибка добавления ведущего: {e}")
        await message.answer("❌ Произошла ошибка при добавлении ведущего.")

@router.message(Command("add_item"))
async def cmd_add_item(message: Message, state: FSMContext):
    """Обработчик команды /add_item"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может добавлять позиции.")
        return
    
    await message.answer("📚 Добавление новой позиции\n\nВведите название:")
    await state.set_state(AdminStates.waiting_for_item_name)

@router.message(AdminStates.waiting_for_item_name)
async def process_item_name(message: Message, state: FSMContext):
    """Обработка названия позиции"""
    await state.update_data(item_name=message.text)
    await message.answer("📂 Введите категорию:")
    await state.set_state(AdminStates.waiting_for_item_category)

@router.message(AdminStates.waiting_for_item_category)
async def process_item_category(message: Message, state: FSMContext):
    """Обработка категории позиции"""
    await state.update_data(item_category=message.text)
    await message.answer("💰 Введите цену (в рублях):")
    await state.set_state(AdminStates.waiting_for_item_price)

@router.message(AdminStates.waiting_for_item_price)
async def process_item_price(message: Message, state: FSMContext):
    """Обработка цены позиции"""
    try:
        price = float(message.text)
        if price < 0:
            await message.answer("❌ Цена не может быть отрицательной.")
            return
        
        await state.update_data(item_price=price)
        await message.answer("📊 Введите минимальный остаток:")
        await state.set_state(AdminStates.waiting_for_item_min_stock)
    except ValueError:
        await message.answer("❌ Введите корректную цену (число).")

@router.message(AdminStates.waiting_for_item_min_stock)
async def process_item_min_stock(message: Message, state: FSMContext):
    """Обработка минимального остатка"""
    try:
        min_stock = int(message.text)
        if min_stock < 0:
            await message.answer("❌ Минимальный остаток не может быть отрицательным.")
            return
        
        data = await state.get_data()
        success = await db.add_item(
            data['item_name'],
            data['item_category'],
            data['item_price'],
            min_stock
        )
        
        if success:
            await message.answer(
                f"✅ Позиция добавлена:\n"
                f"📚 {data['item_name']}\n"
                f"📂 {data['item_category']}\n"
                f"💰 {data['item_price']:.0f} руб.\n"
                f"📊 Мин. остаток: {min_stock} шт."
            )
        else:
            await message.answer("❌ Ошибка при добавлении позиции.")
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректное число для минимального остатка.")

@router.message(Command("update_stock"))
async def cmd_update_stock(message: Message, state: FSMContext):
    """Обработчик команды /update_stock"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может обновлять остатки.")
        return
    
    # Получаем список всех позиций
    report_data = await db.get_stock_report()
    if not report_data:
        await message.answer("❌ Нет позиций для обновления.")
        return
    
    text = "📚 Выберите позицию для обновления остатка:\n\n"
    for i, item in enumerate(report_data, 1):
        text += f"{i}. {item['name']} (текущий остаток: {item['stock']})\n"
    
    await message.answer(text)
    await state.set_state(AdminStates.waiting_for_stock_name)

@router.message(AdminStates.waiting_for_stock_name)
async def process_stock_name(message: Message, state: FSMContext):
    """Обработка названия позиции для обновления остатка"""
    item_name = message.text
    
    # Проверяем, существует ли позиция
    report_data = await db.get_stock_report()
    item_exists = any(item['name'] == item_name for item in report_data)
    
    if not item_exists:
        await message.answer("❌ Позиция не найдена. Проверьте название.")
        return
    
    await state.update_data(stock_name=item_name)
    await message.answer(f"📊 Введите новый остаток для '{item_name}':")
    await state.set_state(AdminStates.waiting_for_stock_count)

@router.message(AdminStates.waiting_for_stock_count)
async def process_stock_count(message: Message, state: FSMContext):
    """Обработка количества для обновления остатка"""
    try:
        count = int(message.text)
        if count < 0:
            await message.answer("❌ Остаток не может быть отрицательным.")
            return
        
        data = await state.get_data()
        item_name = data['stock_name']
        
        success = await db.update_stock(item_name, count)
        if success:
            # Проверяем, не стал ли остаток ниже минимума
            report_data = await db.get_stock_report()
            for item in report_data:
                if item['name'] == item_name and item['stock'] <= item['min_stock']:
                    await message.answer(
                        f"✅ Остаток по {item_name} обновлён: {count} шт.\n\n"
                        f"⚠️ Внимание! Остаток {item_name} ниже минимума ({item['stock']}/{item['min_stock']})."
                    )
                    return
            await message.answer(f"✅ Остаток по {item_name} обновлён: {count} шт.")
        else:
            await message.answer("❌ Ошибка при обновлении остатка.")
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректное число.")

@router.message(Command("report"))
async def cmd_report(message: Message):
    """Обработчик команды /report"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может просматривать отчёты.")
        return
    
    report_data = await db.get_stock_report()
    text = format_stock_report(report_data)
    await message.answer(text)

@router.message(Command("low"))
async def cmd_low(message: Message):
    """Обработчик команды /low"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может просматривать низкие остатки.")
        return
    
    low_stock_data = await db.get_low_stock()
    text = format_low_stock(low_stock_data)
    await message.answer(text)

@router.message(Command("reset_sales"))
async def cmd_reset_sales(message: Message):
    """Обработчик команды /reset_sales"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может обнулять продажи.")
        return
    
    success = await db.reset_sales()
    if success:
        await message.answer("✅ Продажи обнулены. Начинаем новый месяц!")
    else:
        await message.answer("❌ Ошибка при обнулении продаж.")

@router.message(Command("inventory"))
async def cmd_inventory(message: Message):
    """Обработчик команды /inventory - полная инвентаризация"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может проводить инвентаризацию.")
        return
    
    report_data = await db.get_stock_report()
    if not report_data:
        await message.answer("❌ Нет данных для инвентаризации.")
        return
    
    text = "📋 Полная инвентаризация:\n\n"
    total_items = 0
    low_stock_count = 0
    
    for item in report_data:
        name = item['name']
        stock = item['stock']
        min_stock = item['min_stock']
        sold = item['sold']
        price = item['price']
        
        total_items += stock
        if stock <= min_stock:
            low_stock_count += 1
        
        warning = " ⚠️" if stock <= min_stock else ""
        text += f"📚 {name}\n"
        text += f"   Остаток: {stock} шт. (мин: {min_stock}){warning}\n"
        text += f"   Проданно: {sold} шт. на {sold * price:.0f} руб.\n\n"
    
    text += f"📊 Итого позиций: {len(report_data)}\n"
    text += f"📦 Общий остаток: {total_items} шт.\n"
    text += f"⚠️ Низкие остатки: {low_stock_count} позиций"
    
    await message.answer(text)
