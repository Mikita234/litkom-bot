import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
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
    waiting_for_item_cost = State()
    waiting_for_item_min_stock = State()
    waiting_for_stock_name = State()
    waiting_for_stock_count = State()
    waiting_for_arrival_quantity = State()

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
    
    # Проверяем, что команда вызвана в группе
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Команда /add_leader работает только в группах.")
        return
    
    # Проверяем, что пользователь - администратор группы
    try:
        chat_member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        if chat_member.status not in ['creator', 'administrator']:
            await message.answer("❌ Только администраторы группы могут добавлять ведущих.")
            return
    except Exception:
        await message.answer("❌ Ошибка проверки прав администратора.")
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
        await message.answer("💰 Введите себестоимость:")
        await state.set_state(AdminStates.waiting_for_item_cost)
    except ValueError:
        await message.answer("❌ Введите корректную цену (число).")

@router.message(AdminStates.waiting_for_item_cost)
async def process_item_cost(message: Message, state: FSMContext):
    """Обработка себестоимости позиции"""
    try:
        cost = float(message.text)
        if cost < 0:
            await message.answer("❌ Себестоимость не может быть отрицательной.")
            return
        
        await state.update_data(item_cost=cost)
        await message.answer("📊 Введите минимальный остаток:")
        await state.set_state(AdminStates.waiting_for_item_min_stock)
    except ValueError:
        await message.answer("❌ Введите корректную себестоимость (число).")

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
            data['item_cost'],
            min_stock
        )
        
        if success:
            profit_margin = ((data['item_price'] - data['item_cost']) / data['item_price']) * 100
            await message.answer(
                f"✅ Позиция добавлена:\n"
                f"📚 {data['item_name']}\n"
                f"📂 {data['item_category']}\n"
                f"💰 Цена: {data['item_price']:.0f} руб.\n"
                f"💸 Себестоимость: {data['item_cost']:.0f} руб.\n"
                f"📊 Мин. остаток: {min_stock} шт.\n"
                f"💎 Маржа: {profit_margin:.1f}%"
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

@router.message(Command("arrival"))
async def cmd_arrival(message: Message):
    """Приход товара (добавление к остатку)"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может регистрировать приход.")
        return
    
    # Получаем список товаров для выбора
    items = await db.get_all_items()
    if not items:
        await message.answer("❌ Нет товаров в базе данных.")
        return
    
    keyboard = create_items_keyboard(items, "arrival")
    await message.answer(
        "📦 <b>Приход товара</b>\n\n"
        "Выберите товар для добавления к остатку:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

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
    total_revenue = 0
    total_cost = 0
    
    for item in report_data:
        name = item['name']
        stock = item['stock']
        min_stock = item['min_stock']
        sold = item['sold']
        price = item['price']
        cost = item.get('cost', 0)
        
        total_items += stock
        if stock <= min_stock:
            low_stock_count += 1
        
        revenue = sold * price
        item_cost = sold * cost
        profit = revenue - item_cost
        
        total_revenue += revenue
        total_cost += item_cost
        
        warning = " ⚠️" if stock <= min_stock else ""
        text += f"📚 {name}\n"
        text += f"   Остаток: {stock} шт. (мин: {min_stock}){warning}\n"
        text += f"   Проданно: {sold} шт. на {revenue:.0f} руб.\n"
        text += f"   Прибыль: {profit:.0f} руб.\n\n"
    
    total_profit = total_revenue - total_cost
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    text += f"📊 ИТОГО:\n"
    text += f"   Позиций: {len(report_data)}\n"
    text += f"   Остаток: {total_items} шт.\n"
    text += f"   Низкие остатки: {low_stock_count}\n"
    text += f"   Выручка: {total_revenue:.0f} руб.\n"
    text += f"   Затраты: {total_cost:.0f} руб.\n"
    text += f"   Прибыль: {total_profit:.0f} руб. ({profit_margin:.1f}%)"
    
    await message.answer(text)

@router.message(Command("analytics"))
async def cmd_analytics(message: Message):
    """Обработчик команды /analytics - аналитика спроса"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может просматривать аналитику.")
        return
    
    import datetime
    current_date = datetime.date.today()
    current_year = current_date.year
    current_month = current_date.month
    
    # Предыдущий месяц
    if current_month == 1:
        prev_year = current_year - 1
        prev_month = 12
    else:
        prev_year = current_year
        prev_month = current_month - 1
    
    analytics_data = await db.get_demand_analytics(
        current_year, current_month, prev_year, prev_month
    )
    
    if not analytics_data:
        await message.answer("❌ Недостаточно данных для аналитики. Нужны данные за минимум 2 месяца.")
        return
    
    current_period = f"{current_month}.{current_year}"
    previous_period = f"{prev_month}.{prev_year}"
    
    from utils import format_demand_analytics
    text = format_demand_analytics(analytics_data, current_period, previous_period)
    await message.answer(text)

@router.message(Command("profit"))
async def cmd_profit(message: Message):
    """Обработчик команды /profit - отчет по прибыли"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может просматривать отчет по прибыли.")
        return
    
    profit_data = await db.get_profit_report()
    from utils import format_profit_report
    text = format_profit_report(profit_data)
    await message.answer(text)

# Обработчик выбора товара для прихода
@router.callback_query(F.data.startswith("arrival_"))
async def process_arrival_item_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора товара для прихода"""
    item_id = int(callback.data.split("_")[1])
    
    # Получаем информацию о товаре
    item = await db.get_item_by_id(item_id)
    if not item:
        await callback.answer("❌ Товар не найден")
        return
    
    # Сохраняем ID товара в состоянии
    await state.update_data(arrival_item_id=item_id)
    await state.set_state(AdminStates.waiting_for_arrival_quantity)
    
    await callback.message.edit_text(
        f"📦 <b>Приход товара</b>\n\n"
        f"Товар: <b>{item['name']}</b>\n"
        f"Текущий остаток: <b>{item['stock']} шт.</b>\n\n"
        f"Введите количество для добавления к остатку:",
        parse_mode="HTML"
    )
    await callback.answer()

# Обработчик ввода количества для прихода
@router.message(AdminStates.waiting_for_arrival_quantity)
async def process_arrival_quantity(message: Message, state: FSMContext):
    """Обработка ввода количества для прихода"""
    try:
        quantity = int(message.text)
        if quantity <= 0:
            await message.answer("❌ Количество должно быть больше 0. Попробуйте снова:")
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        item_id = data.get('arrival_item_id')
        
        if not item_id:
            await message.answer("❌ Ошибка. Начните заново с команды /arrival")
            await state.clear()
            return
        
        # Получаем информацию о товаре
        item = await db.get_item_by_id(item_id)
        if not item:
            await message.answer("❌ Товар не найден")
            await state.clear()
            return
        
        # Обновляем остаток
        new_stock = item['stock'] + quantity
        success = await db.update_stock(item['name'], new_stock)
        
        if success:
            await message.answer(
                f"✅ <b>Приход зарегистрирован</b>\n\n"
                f"Товар: <b>{item['name']}</b>\n"
                f"Добавлено: <b>+{quantity} шт.</b>\n"
                f"Новый остаток: <b>{new_stock} шт.</b>",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка при обновлении остатка")
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите корректное число. Попробуйте снова:")
    except Exception as e:
        logger.error(f"Ошибка при обработке прихода: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте снова.")
        await state.clear()
