"""Запись на консультацию: FSM-анкета, сохранение заявки, уведомление менеджеру."""

import logging
import re
from html import escape as escape_html

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import config
from database import add_booking, get_user, missing_tests, upsert_user
from keyboards import (
    booking_confirm_kb,
    booking_format_kb,
    channel_kb,
    main_menu_kb,
    test_actions_kb,
)
from tests_data import TEST_LABELS, results_for_manager

router = Router()
logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^@[A-Za-z0-9_]{4,32}$")
PHONE_RE = re.compile(r"^\+?\d{7,15}$")


class Booking(StatesGroup):
    """Шаги анкеты записи на консультацию."""

    name = State()
    time = State()
    channel = State()
    contact = State()
    confirm = State()


def _gate_text(missing: list[str]) -> str:
    bullets = "\n".join(f"• {TEST_LABELS[key]}" for key in missing)
    return (
        "🔒 <b>Запись на консультацию пока недоступна</b>\n\n"
        "Чтобы записаться, нужно пройти все три теста — тогда консультант уже будет знать "
        "о вас больше, и сессия пройдёт эффективнее.\n\n"
        f"Осталось пройти:\n{bullets}\n\n"
        "Выберите тест кнопкой ниже 👇"
    )


async def _ask_name(message: Message, state: FSMContext) -> None:
    await state.set_state(Booking.name)
    await message.answer(
        "📝 <b>Запись на консультацию</b>\n\n"
        "<b>Шаг 1 из 4.</b> Как к вам обращаться?\n\n"
        "Введите имя (или имя и фамилию). Отменить можно командой /cancel "
        "или кнопками меню.",
    )


async def handle_booking_request(message: Message, state: FSMContext) -> None:
    """Проверяет «гейтинг» и либо пускает к анкете, либо просит доделать тесты."""
    await state.clear()
    user = get_user(message.from_user.id)
    missing = missing_tests(user)
    if missing:
        await message.answer(_gate_text(missing), reply_markup=test_actions_kb(user))
        return
    await _ask_name(message, state)


@router.callback_query(F.data == "booking:start")
async def cb_booking_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = get_user(callback.from_user.id)
    missing = missing_tests(user)
    if missing:
        await callback.message.answer(_gate_text(missing), reply_markup=test_actions_kb(user))
    else:
        await _ask_name(callback.message, state)
    await callback.answer()


@router.message(Booking.name, F.text)
async def process_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 60 or "\n" in name:
        await message.answer("Пожалуйста, введите имя — от 2 до 60 символов:")
        return
    await state.update_data(name=name)
    await state.set_state(Booking.time)
    await message.answer(
        "⏰ <b>Шаг 2 из 4.</b> В какое время вам удобно, чтобы мы связались?\n\n"
        "Например: «будни после 18:00», «суббота утром», «в любое время»."
    )


@router.message(Booking.time, F.text)
async def process_time(message: Message, state: FSMContext) -> None:
    preferred_time = message.text.strip()
    if not 3 <= len(preferred_time) <= 200:
        await message.answer(
            "Опишите удобное время подробнее (от 3 до 200 символов). "
            "Например: «будни после 18:00»:"
        )
        return
    await state.update_data(time=preferred_time)
    await state.set_state(Booking.channel)
    await message.answer(
        "💬 <b>Шаг 3 из 4.</b> Выберите удобный формат связи:",
        reply_markup=booking_format_kb(),
    )


@router.callback_query(Booking.channel, F.data.startswith("bkfmt:"))
async def process_channel(callback: CallbackQuery, state: FSMContext) -> None:
    channel = callback.data.split(":")[1]
    if channel not in ("telegram", "whatsapp"):
        await callback.answer()
        return
    await state.update_data(channel=channel)
    await state.set_state(Booking.contact)
    channel_name = "Telegram" if channel == "telegram" else "WhatsApp"
    await callback.message.answer(
        f"📞 <b>Шаг 4 из 4.</b> Оставьте контакт для связи через {channel_name}.\n\n"
        "Номер телефона (например, <code>+7 999 123-45-67</code>) "
        "или @username в Telegram:"
    )
    await callback.answer()


def _is_valid_contact(text: str) -> bool:
    if USERNAME_RE.match(text):
        return True
    compact = re.sub(r"[\s\-()]", "", text)
    return bool(PHONE_RE.match(compact))


@router.message(Booking.contact, F.text)
async def process_contact(message: Message, state: FSMContext) -> None:
    contact = message.text.strip()
    if not _is_valid_contact(contact):
        await message.answer(
            "Не похоже на телефон или username 🤔\n"
            "Укажите номер в формате <code>+79991234567</code> или @username:"
        )
        return
    await state.update_data(contact=contact)
    await state.set_state(Booking.confirm)
    data = await state.get_data()
    await message.answer(_booking_summary(data), reply_markup=booking_confirm_kb())


def _booking_summary(data: dict) -> str:
    channel_name = "Telegram" if data["channel"] == "telegram" else "WhatsApp"
    return (
        "📋 <b>Проверьте заявку</b>\n\n"
        f"👤 <b>Имя:</b> {escape_html(data['name'])}\n"
        f"⏰ <b>Удобное время:</b> {escape_html(data['time'])}\n"
        f"💬 <b>Формат связи:</b> {channel_name}\n"
        f"📞 <b>Контакт:</b> {escape_html(data['contact'])}\n\n"
        "Всё верно? Отправляем заявку консультанту?"
    )


@router.callback_query(Booking.confirm, F.data == "bk:confirm")
async def cb_booking_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    tg_user = callback.from_user

    upsert_user(tg_user.id, tg_user.username, tg_user.full_name)
    booking_id = add_booking(
        telegram_id=tg_user.id,
        name=data["name"],
        preferred_time=data["time"],
        contact_channel=data["channel"],
        contact=data["contact"],
    )
    user = get_user(tg_user.id)
    await _notify_manager(bot, tg_user, data, user)

    await callback.message.edit_text(
        "✅ <b>Спасибо! Мы свяжемся с вами в ближайшее время.</b>\n\n"
        f"Заявка №{booking_id} принята. А пока можете подписаться "
        "на наш канал о профориентации 📢",
        reply_markup=channel_kb(),
    )
    await callback.message.answer("🏠 Главное меню:", reply_markup=main_menu_kb(user))
    await callback.answer("Заявка отправлена ✅")


@router.callback_query(F.data == "bk:cancel")
async def cb_booking_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = get_user(callback.from_user.id)
    await callback.message.edit_text("❌ Заявка отменена.")
    await callback.message.answer(
        "Вы можете начать запись заново в любой момент 👇",
        reply_markup=main_menu_kb(user),
    )
    await callback.answer()


async def _notify_manager(bot: Bot, tg_user, data: dict, user: dict | None) -> None:
    """Отправляет менеджеру детали заявки и сводку результатов тестов."""
    if not config.manager_chat_id:
        logger.warning("MANAGER_CHAT_ID не задан — уведомление о заявке не отправлено")
        return

    channel_name = "Telegram" if data["channel"] == "telegram" else "WhatsApp"
    username = f"@{tg_user.username}" if tg_user.username else "—"
    results = results_for_manager(user) or "результаты тестов не найдены"
    text = (
        "🆕 <b>Новая заявка на консультацию!</b>\n\n"
        f"👤 <b>Имя:</b> {escape_html(data['name'])}\n"
        f"⏰ <b>Удобное время:</b> {escape_html(data['time'])}\n"
        f"💬 <b>Формат связи:</b> {channel_name}\n"
        f"📞 <b>Контакт:</b> {escape_html(data['contact'])}\n\n"
        f"🧑‍💻 <b>Клиент в Telegram:</b> {username} "
        f"(id: <code>{tg_user.id}</code>)\n\n"
        f"📊 <b>Результаты тестов:</b>\n{results}"
    )
    try:
        await bot.send_message(config.manager_chat_id, text)
    except Exception:
        logger.exception("Не удалось отправить уведомление менеджеру")
