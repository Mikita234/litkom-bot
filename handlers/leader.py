import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from db import db
from utils import format_price_list

logger = logging.getLogger(__name__)
router = Router()

# Этот файл содержит обработчики, специфичные для ведущих
# Основные команды ведущих уже реализованы в common.py

@router.message(Command("leader_help"))
async def cmd_leader_help(message: Message):
    """Дополнительная справка для ведущих"""
    if not await db.is_leader(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    text = (
        "📚 Дополнительная справка для ведущих:\n\n"
        "💡 Советы по работе:\n"
        "• Используйте /price для быстрого просмотра цен\n"
        "• Команда /sell позволяет легко отметить продажу\n"
        "• /stock показывает актуальные остатки\n"
        "• Бот работает в группах и ветках\n\n"
        "🔔 Уведомления:\n"
        "• При низких остатках бот предупредит\n"
        "• Все продажи логируются автоматически\n"
        "• Остатки обновляются в реальном времени"
    )
    
    await message.answer(text)
