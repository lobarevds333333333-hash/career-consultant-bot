"""Все клавиатуры бота: reply-меню и inline-кнопки."""

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import config
from database import completed_tests, missing_tests
from tests_data import TEST_LABELS, TEST_ORDER


def main_menu_kb(user: dict | None) -> ReplyKeyboardMarkup:
    """Основное reply-меню; пройденные тесты помечаются галочкой."""
    builder = ReplyKeyboardBuilder()
    done = completed_tests(user)
    for key in TEST_ORDER:
        prefix = "✅ " if key in done else ""
        builder.button(text=f"{prefix}{TEST_LABELS[key]}")
    builder.button(text="📊 Мои результаты")
    builder.button(text="📅 Запись на консультацию")
    builder.button(text="📢 Наш Telegram-канал")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выберите действие…",
    )


def test_intro_kb(test_key: str) -> InlineKeyboardMarkup:
    """Кнопки под инструкцией перед тестом."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Начать тест", callback_data=f"test:start:{test_key}")
    builder.button(text="⏹ Отмена", callback_data="test:cancel")
    builder.adjust(1)
    return builder.as_markup()


def question_kb(test_key: str, question_index: int, options: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Inline-кнопки вариантов ответа на вопрос теста."""
    builder = InlineKeyboardBuilder()
    for option_key, label in options:
        builder.button(
            text=label,
            callback_data=f"ans:{test_key}:{question_index}:{option_key}",
        )
    builder.button(text="⏹ Прервать тест", callback_data="test:cancel")
    builder.adjust(1)
    return builder.as_markup()


def test_actions_kb(user: dict | None) -> InlineKeyboardMarkup:
    """Кнопки «что дальше» после теста / в сводке результатов / при блокировке записи."""
    builder = InlineKeyboardBuilder()
    missing = missing_tests(user)
    for key in missing:
        builder.button(
            text=f"🧪 Пройти: {TEST_LABELS[key]}",
            callback_data=f"test:intro:{key}",
        )
    if not missing:
        builder.button(text="📅 Записаться на консультацию", callback_data="booking:start")
    builder.button(text="🏠 Главное меню", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


def channel_kb() -> InlineKeyboardMarkup:
    """Кнопка-ссылка на Telegram-канал."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Перейти в канал", url=config.channel_url)
    return builder.as_markup()


def booking_format_kb() -> InlineKeyboardMarkup:
    """Выбор формата связи для заявки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✈️ Telegram", callback_data="bkfmt:telegram")
    builder.button(text="💬 WhatsApp", callback_data="bkfmt:whatsapp")
    builder.adjust(2)
    return builder.as_markup()


def booking_confirm_kb() -> InlineKeyboardMarkup:
    """Подтверждение заявки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить заявку", callback_data="bk:confirm")
    builder.button(text="✖️ Отменить", callback_data="bk:cancel")
    builder.adjust(2)
    return builder.as_markup()
