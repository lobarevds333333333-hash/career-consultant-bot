"""Общие обработчики: /start, /help, /cancel, пункты главного меню и fallback."""

from html import escape as escape_html

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardMarkup

from database import get_user, upsert_user
from handlers.booking import handle_booking_request
from keyboards import channel_kb, main_menu_kb, test_intro_kb, test_actions_kb
from tests_data import TEST_INTROS, results_overview_text

router = Router()
# Отдельный роутер для «хвостовых» обработчиков — подключается в bot.py последним
fallback_router = Router()

WELCOME_TEMPLATE = (
    "👋 <b>Привет, {name}!</b>\n\n"
    "Я — бот-помощник карьерного консультанта. Помогу лучше понять себя "
    "и подготовиться к консультации.\n\n"
    "🧪 <b>Тест на профориентацию</b> — узнаете свои профессиональные склонности;\n"
    "🧩 <b>Тест на тип мышления</b> — определите, как вам удобнее думать и решать задачи;\n"
    "💡 <b>Тест на мотивацию</b> — поймёте, что движет вами в работе.\n\n"
    "📌 <b>Пройдите все три теста</b> — и вам откроется запись на консультацию. "
    "Тесты можно проходить в любом порядке, результаты сохраняются.\n\n"
    "📢 А ещё у нас есть Telegram-канал о профориентации — ссылка в меню.\n\n"
    "Выберите действие на клавиатуре ниже 👇"
)

HELP_TEXT = (
    "ℹ️ <b>Как пользоваться ботом</b>\n\n"
    "/start — приветствие и главное меню\n"
    "/cancel — отменить текущее действие (тест или заявку)\n\n"
    "📌 Порядок работы:\n"
    "1. Пройдите три теста в любом порядке: профориентацию, тип мышления, мотивацию.\n"
    "2. Посмотрите итоги кнопкой «📊 Мои результаты».\n"
    "3. После всех трёх тестов станет доступна «📅 Запись на консультацию».\n\n"
    "📢 Подписывайтесь на наш Telegram-канал — там статьи о профориентации и карьере."
)

CHANNEL_TEXT = (
    "📢 <b>Наш Telegram-канал о профориентации</b>\n\n"
    "Мы публикуем разборы профессий, советы по построению карьеры "
    "и реальные истории клиентов. Подписывайтесь, чтобы ничего не пропустить 👇"
)


def _menu_kb(message: Message) -> ReplyKeyboardMarkup:
    return main_menu_kb(get_user(message.from_user.id))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    tg_user = message.from_user
    upsert_user(tg_user.id, tg_user.username, tg_user.full_name)
    name = escape_html(tg_user.first_name or "друг")
    await message.answer(
        WELCOME_TEMPLATE.format(name=name),
        reply_markup=main_menu_kb(get_user(tg_user.id)),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(HELP_TEXT, reply_markup=_menu_kb(message))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено. Вы в главном меню 👇", reply_markup=_menu_kb(message))


@router.message(F.text.endswith("Профориентация"))
async def menu_career(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(TEST_INTROS["career"], reply_markup=test_intro_kb("career"))


@router.message(F.text.endswith("Тип мышления"))
async def menu_thinking(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(TEST_INTROS["thinking"], reply_markup=test_intro_kb("thinking"))


@router.message(F.text.endswith("Мотивация"))
async def menu_motivation(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(TEST_INTROS["motivation"], reply_markup=test_intro_kb("motivation"))


@router.message(F.text.endswith("Мои результаты"))
async def menu_results(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = get_user(message.from_user.id)
    await message.answer(results_overview_text(user), reply_markup=test_actions_kb(user))


@router.message(F.text.endswith("Запись на консультацию"))
async def menu_booking(message: Message, state: FSMContext) -> None:
    await handle_booking_request(message, state)


@router.message(F.text.endswith("Telegram-канал"))
async def menu_channel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(CHANNEL_TEXT, reply_markup=channel_kb())


@router.callback_query(F.data == "menu:home")
async def cb_menu_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = get_user(callback.from_user.id)
    await callback.message.answer("🏠 Вы в главном меню 👇", reply_markup=main_menu_kb(user))
    await callback.answer()


# --- Хвостовые обработчики: всё, что не распознано выше ---

@fallback_router.message()
async def unknown_message(message: Message) -> None:
    await message.answer(
        "🤔 Я не понял это сообщение. Выберите действие кнопками меню ниже "
        "или отправьте /start.",
        reply_markup=_menu_kb(message),
    )


@fallback_router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    # Старые кнопки от уже обработанных сообщений — просто закрываем «часики»
    await callback.answer()
