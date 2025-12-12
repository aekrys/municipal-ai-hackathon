from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage  # Добавьте это
import asyncio
import os
import logging  # Добавьте логирование
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN не найден в .env файле!")
    exit(1)

# Используйте MemoryStorage для состояний (если они понадобятся в будущем)
storage = MemoryStorage()
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=storage)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Команда для запуска мини-приложения"""
    # URL вашего задеплоенного мини-приложения
    web_app_url = "https://municipal-ai-assistant.netlify.app/"  # Замените на ваш реальный URL

    web_app = types.WebAppInfo(url=web_app_url)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[
            types.InlineKeyboardButton(
                text="🚀 Открыть AI-помощник Главы",
                web_app=web_app
            )
        ]]
    )

    await message.answer(
        "👋 Добро пожаловать в систему мониторинга муниципальных проблем!\n\n"
        "Нажмите кнопку ниже, чтобы открыть интерактивное приложение для анализа "
        "обращений граждан и принятия управленческих решений:",
        reply_markup=keyboard
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда помощи"""
    await message.answer(
        "ℹ️ *Доступные команды:*\n"
        "/start - запустить мини-приложение\n"
        "/help - показать это сообщение\n\n"
        "*Как использовать:*\n"
        "1. Нажмите /start\n"
        "2. Нажмите кнопку 'Открыть AI-помощник'\n"
        "3. В открывшемся окне работайте с аналитикой обращений",
        parse_mode="Markdown"
    )


@dp.message()
async def handle_other_messages(message: types.Message):
    """Обработка всех остальных сообщений"""
    await message.answer(
        "Для работы с системой используйте команду /start\n"
        "Нужна помощь? Напишите /help"
    )


async def main():
    logger.info("🤖 Telegram бот запускается...")

    # Удаляем вебхук на всякий случай (если он был)
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("✅ Бот запущен. Ожидаем сообщений...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")