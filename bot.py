"""Точка входа: сборка диспетчера aiogram и запуск long polling."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database import init_db
from handlers import booking, common, tests

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    init_db()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: команды и меню → тесты → заявка → «хвостовые» обработчики
    dp.include_routers(
        common.router,
        tests.router,
        booking.router,
        common.fallback_router,
    )

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен, ожидаем сообщения…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
