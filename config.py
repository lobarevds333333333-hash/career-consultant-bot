"""Загрузка настроек бота из переменных окружения (.env)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    manager_chat_id: int
    channel_url: str
    db_path: str


def _to_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def load_config() -> Config:
    token = (os.getenv("BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(
            "BOT_TOKEN не задан. Создайте файл .env на основе .env.example "
            "и укажите токен, полученный у @BotFather."
        )
    return Config(
        bot_token=token,
        manager_chat_id=_to_int(os.getenv("MANAGER_CHAT_ID")),
        channel_url=os.getenv("CHANNEL_URL", "https://t.me/proforientation").strip(),
        db_path=os.getenv("DB_PATH", "career_bot.db").strip() or "career_bot.db",
    )


config = load_config()
