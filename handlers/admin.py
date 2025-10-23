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
from utils import format_stock_report, format_low_stock

logger = logging.getLogger(__name__)
router = Router()

# Универсальная функция для очистки состояния при командах
async def clear_state_on_command(message: Message, state: FSMContext):
    """Очищает состояние FSM если пользователь отправил команду"""
    if message.text and message.text.startswith('/'):
        await state.clear()
        return True
    return False

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
    # Новые состояния для редактирования
    waiting_for_edit_item_selection = State()
    waiting_for_edit_field = State()
    waiting_for_edit_value = State()
    waiting_for_delete_item_selection = State()
    waiting_for_change_price_item = State()
    waiting_for_change_price_value = State()
    waiting_for_change_name_item = State()
    waiting_for_change_name_value = State()

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
    if await clear_state_on_command(message, state):
        return
    
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
    if await clear_state_on_command(message, state):
        return
    
    await state.update_data(item_name=message.text)
    await message.answer("📂 Введите категорию:")
    await state.set_state(AdminStates.waiting_for_item_category)

@router.message(AdminStates.waiting_for_item_category)
async def process_item_category(message: Message, state: FSMContext):
    """Обработка категории позиции"""
    if await clear_state_on_command(message, state):
        return
    
    await state.update_data(item_category=message.text)
    await message.answer("💰 Введите цену (в злотых):")
    await state.set_state(AdminStates.waiting_for_item_price)

@router.message(AdminStates.waiting_for_item_price)
async def process_item_price(message: Message, state: FSMContext):
    """Обработка цены позиции"""
    if await clear_state_on_command(message, state):
        return
    
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
    if await clear_state_on_command(message, state):
        return
    
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
    if await clear_state_on_command(message, state):
        return
    
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
                f"💰 Цена: {data['item_price']:.0f} zł\n"
                f"💸 Себестоимость: {data['item_cost']:.0f} zł\n"
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
    # Если это команда, не обрабатываем здесь
    if message.text and message.text.startswith('/'):
        await state.clear()
        return
    
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
    if await clear_state_on_command(message, state):
        return
    
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
    """Обработчик команды /reset_sales - НЕ обнуляем, а архивируем данные"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может архивировать данные.")
        return
    
    # Вместо обнуления - архивируем данные в monthly_sales
    success = await db.archive_monthly_sales()
    if success:
        await message.answer(
            "✅ <b>Данные за месяц архивированы!</b>\n\n"
            "📊 Продажи сохранены в истории\n"
            "📈 Доступны для аналитики\n"
            "🔄 Можно начинать новый период",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка при архивировании данных.")

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
        text += f"   Проданно: {sold} шт. на {revenue:.0f} zł\n"
        text += f"   Прибыль: {profit:.0f} zł\n\n"
    
    total_profit = total_revenue - total_cost
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    text += f"📊 ИТОГО:\n"
    text += f"   Позиций: {len(report_data)}\n"
    text += f"   Остаток: {total_items} шт.\n"
    text += f"   Низкие остатки: {low_stock_count}\n"
    text += f"   Выручка: {total_revenue:.0f} zł\n"
    text += f"   Затраты: {total_cost:.0f} zł\n"
    text += f"   Прибыль: {total_profit:.0f} zł ({profit_margin:.1f}%)"
    
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
    if await clear_state_on_command(message, state):
        return
    
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

# ===== НОВЫЕ КОМАНДЫ ДЛЯ РЕДАКТИРОВАНИЯ ТОВАРОВ =====

@router.message(Command("edit_item"))
async def cmd_edit_item(message: Message, state: FSMContext):
    """Обработчик команды /edit_item"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может редактировать товары.")
        return
    
    # Получаем список всех товаров
    items = await db.get_all_items()
    if not items:
        await message.answer("📚 Нет товаров для редактирования.")
        return
    
    # Создаем клавиатуру с товарами
    from utils import create_items_keyboard
    keyboard = create_items_keyboard(items, "edit_item")
    
    await message.answer(
        "📝 <b>Выберите товар для редактирования:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_edit_item_selection)

@router.callback_query(F.data.startswith("edit_item_"))
async def process_edit_item_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора товара для редактирования"""
    if await clear_state_on_command(callback.message, state):
        return
    
    item_id = int(callback.data.split("_")[2])
    item = await db.get_item_by_id(item_id)
    
    if not item:
        await callback.message.edit_text("❌ Товар не найден.")
        return
    
    await state.update_data(edit_item_id=item_id)
    
    # Создаем клавиатуру с полями для редактирования
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Название", callback_data="edit_field_name")],
        [InlineKeyboardButton(text="📂 Категория", callback_data="edit_field_category")],
        [InlineKeyboardButton(text="💰 Цена", callback_data="edit_field_price")],
        [InlineKeyboardButton(text="💸 Себестоимость", callback_data="edit_field_cost")],
        [InlineKeyboardButton(text="📊 Мин. остаток", callback_data="edit_field_min_stock")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_cancel")]
    ])
    
    await callback.message.edit_text(
        f"📝 <b>Редактирование товара:</b>\n\n"
        f"<b>Название:</b> {item['name']}\n"
        f"<b>Категория:</b> {item['category']}\n"
        f"<b>Цена:</b> {item['price']} zł\n"
        f"<b>Себестоимость:</b> {item['cost']} zł\n"
        f"<b>Мин. остаток:</b> {item['min_stock']} шт.\n\n"
        f"<b>Выберите поле для редактирования:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_edit_field)

@router.callback_query(F.data.startswith("edit_field_"))
async def process_edit_field_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора поля для редактирования"""
    if await clear_state_on_command(callback.message, state):
        return
    
    field = callback.data.split("_")[2]
    field_names = {
        "name": "название",
        "category": "категорию", 
        "price": "цену",
        "cost": "себестоимость",
        "min_stock": "минимальный остаток"
    }
    
    await state.update_data(edit_field=field)
    
    await callback.message.edit_text(
        f"✏️ <b>Введите новое {field_names[field]}:</b>",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_edit_value)

@router.message(AdminStates.waiting_for_edit_value)
async def process_edit_value(message: Message, state: FSMContext):
    """Обработка нового значения поля"""
    if await clear_state_on_command(message, state):
        return
    
    data = await state.get_data()
    item_id = data.get('edit_item_id')
    field = data.get('edit_field')
    new_value = message.text
    
    # Валидация в зависимости от поля
    if field in ['price', 'cost']:
        try:
            new_value = float(new_value)
            if new_value < 0:
                await message.answer("❌ Значение не может быть отрицательным.")
                return
        except ValueError:
            await message.answer("❌ Введите корректное число.")
            return
    elif field == 'min_stock':
        try:
            new_value = int(new_value)
            if new_value < 0:
                await message.answer("❌ Минимальный остаток не может быть отрицательным.")
                return
        except ValueError:
            await message.answer("❌ Введите корректное число.")
            return
    
    # Обновляем товар
    update_data = {field: new_value}
    success = await db.update_item(item_id, **update_data)
    
    if success:
        await message.answer(f"✅ Товар успешно обновлен!")
    else:
        await message.answer("❌ Ошибка при обновлении товара.")
    
    await state.clear()

@router.callback_query(F.data == "edit_cancel")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования"""
    await callback.message.edit_text("❌ Редактирование отменено.")
    await state.clear()

@router.message(Command("delete_item"))
async def cmd_delete_item(message: Message, state: FSMContext):
    """Обработчик команды /delete_item"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может удалять товары.")
        return
    
    # Получаем список всех товаров
    items = await db.get_all_items()
    if not items:
        await message.answer("📚 Нет товаров для удаления.")
        return
    
    # Создаем клавиатуру с товарами
    from utils import create_items_keyboard
    keyboard = create_items_keyboard(items, "delete_item")
    
    await message.answer(
        "🗑️ <b>Выберите товар для удаления:</b>\n\n"
        "⚠️ <b>Внимание:</b> Товар будет удален навсегда!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_delete_item_selection)

@router.callback_query(F.data.startswith("delete_item_"))
async def process_delete_item_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка удаления товара"""
    if await clear_state_on_command(callback.message, state):
        return
    
    item_id = int(callback.data.split("_")[2])
    item = await db.get_item_by_id(item_id)
    
    if not item:
        await callback.message.edit_text("❌ Товар не найден.")
        return
    
    # Создаем клавиатуру подтверждения
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{item_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")]
    ])
    
    await callback.message.edit_text(
        f"🗑️ <b>Подтвердите удаление:</b>\n\n"
        f"<b>Товар:</b> {item['name']}\n"
        f"<b>Категория:</b> {item['category']}\n"
        f"<b>Остаток:</b> {item['stock']} шт.\n\n"
        f"⚠️ <b>Это действие нельзя отменить!</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_item(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления товара"""
    if await clear_state_on_command(callback.message, state):
        return
    
    item_id = int(callback.data.split("_")[2])
    success = await db.delete_item(item_id)
    
    if success:
        await callback.message.edit_text("✅ Товар успешно удален!")
    else:
        await callback.message.edit_text("❌ Ошибка при удалении товара.")
    
    await state.clear()

@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления"""
    await callback.message.edit_text("❌ Удаление отменено.")
    await state.clear()

@router.message(Command("change_price"))
async def cmd_change_price(message: Message, state: FSMContext):
    """Обработчик команды /change_price"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может изменять цены.")
        return
    
    # Получаем список всех товаров
    items = await db.get_all_items()
    if not items:
        await message.answer("📚 Нет товаров для изменения цены.")
        return
    
    # Создаем клавиатуру с товарами
    from utils import create_items_keyboard
    keyboard = create_items_keyboard(items, "change_price")
    
    await message.answer(
        "💰 <b>Выберите товар для изменения цены:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_change_price_item)

@router.callback_query(F.data.startswith("change_price_"))
async def process_change_price_item(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора товара для изменения цены"""
    if await clear_state_on_command(callback.message, state):
        return
    
    item_id = int(callback.data.split("_")[2])
    item = await db.get_item_by_id(item_id)
    
    if not item:
        await callback.message.edit_text("❌ Товар не найден.")
        return
    
    await state.update_data(change_price_item_id=item_id)
    
    await callback.message.edit_text(
        f"💰 <b>Изменение цены товара:</b>\n\n"
        f"<b>Товар:</b> {item['name']}\n"
        f"<b>Текущая цена:</b> {item['price']} zł\n\n"
        f"<b>Введите новую цену:</b>",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_change_price_value)

@router.message(AdminStates.waiting_for_change_price_value)
async def process_change_price_value(message: Message, state: FSMContext):
    """Обработка новой цены"""
    if await clear_state_on_command(message, state):
        return
    
    try:
        new_price = float(message.text)
        if new_price < 0:
            await message.answer("❌ Цена не может быть отрицательной.")
            return
        
        data = await state.get_data()
        item_id = data.get('change_price_item_id')
        
        success = await db.update_item(item_id, price=new_price)
        
        if success:
            await message.answer(f"✅ Цена успешно изменена на {new_price} zł!")
        else:
            await message.answer("❌ Ошибка при изменении цены.")
        
    except ValueError:
        await message.answer("❌ Введите корректную цену (число).")
        return
    
    await state.clear()

@router.message(Command("change_name"))
async def cmd_change_name(message: Message, state: FSMContext):
    """Обработчик команды /change_name"""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может изменять названия.")
        return
    
    # Получаем список всех товаров
    items = await db.get_all_items()
    if not items:
        await message.answer("📚 Нет товаров для изменения названия.")
        return
    
    # Создаем клавиатуру с товарами
    from utils import create_items_keyboard
    keyboard = create_items_keyboard(items, "change_name")
    
    await message.answer(
        "📝 <b>Выберите товар для изменения названия:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_change_name_item)

@router.callback_query(F.data.startswith("change_name_"))
async def process_change_name_item(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора товара для изменения названия"""
    if await clear_state_on_command(callback.message, state):
        return
    
    item_id = int(callback.data.split("_")[2])
    item = await db.get_item_by_id(item_id)
    
    if not item:
        await callback.message.edit_text("❌ Товар не найден.")
        return
    
    await state.update_data(change_name_item_id=item_id)
    
    await callback.message.edit_text(
        f"📝 <b>Изменение названия товара:</b>\n\n"
        f"<b>Текущее название:</b> {item['name']}\n\n"
        f"<b>Введите новое название:</b>",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_change_name_value)

@router.message(AdminStates.waiting_for_change_name_value)
async def process_change_name_value(message: Message, state: FSMContext):
    """Обработка нового названия"""
    if await clear_state_on_command(message, state):
        return
    
    new_name = message.text.strip()
    if not new_name:
        await message.answer("❌ Название не может быть пустым.")
        return
    
    data = await state.get_data()
    item_id = data.get('change_name_item_id')
    
    success = await db.update_item(item_id, name=new_name)
    
    if success:
        await message.answer(f"✅ Название успешно изменено на '{new_name}'!")
    else:
        await message.answer("❌ Ошибка при изменении названия.")
    
    await state.clear()
