"""Обработчики прохождения трёх тестов (inline-кнопки вопросов, подсчёт, сохранение)."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import get_user, save_test_result
from keyboards import main_menu_kb, question_kb, test_actions_kb, test_intro_kb
from tests_data import (
    CAREER_OPTIONS,
    RESULT_BUILDERS,
    TEST_INTROS,
    TEST_QUESTIONS,
    TEST_STEMS,
    progress_text,
)

router = Router()


class TestFlow(StatesGroup):
    """Состояние прохождения теста: ключ теста, номер вопроса, ответы."""

    answering = State()


def _question_options(test_key: str, question: dict) -> list[tuple[str, str]]:
    if test_key == "career":
        return [(key, label) for key, label, _points in CAREER_OPTIONS]
    return list(question["options"])


async def send_test_intro(message: Message, test_key: str) -> None:
    """Показывает инструкцию перед началом теста."""
    await message.answer(TEST_INTROS[test_key], reply_markup=test_intro_kb(test_key))


async def _send_question(message: Message, test_key: str, question_index: int) -> None:
    await message.answer(
        _question_text(test_key, question_index),
        reply_markup=_question_reply_markup(test_key, question_index),
    )


@router.callback_query(F.data.startswith("test:intro:"))
async def cb_test_intro(callback: CallbackQuery, state: FSMContext) -> None:
    test_key = callback.data.removeprefix("test:intro:")
    if test_key not in TEST_INTROS:
        await callback.answer("Неизвестный тест", show_alert=True)
        return
    await state.clear()
    await send_test_intro(callback.message, test_key)
    await callback.answer()


@router.callback_query(F.data == "test:cancel")
async def cb_test_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = get_user(callback.from_user.id)
    await callback.message.answer(
        "⏹ Тест прерван. Вы можете продолжить его в любой момент — прогресс по пройденным "
        "тестам сохраняется.",
        reply_markup=main_menu_kb(user),
    )
    await callback.answer("Тест прерван")


@router.callback_query(F.data.startswith("test:start:"))
async def cb_test_start(callback: CallbackQuery, state: FSMContext) -> None:
    test_key = callback.data.removeprefix("test:start:")
    if test_key not in TEST_QUESTIONS:
        await callback.answer("Неизвестный тест", show_alert=True)
        return
    await state.set_state(TestFlow.answering)
    await state.update_data(test_key=test_key, question_index=0, answers=[])
    await _send_question(callback.message, test_key, 0)
    await callback.answer()


@router.callback_query(TestFlow.answering, F.data.startswith("ans:"))
async def cb_answer(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    test_key = data.get("test_key")
    question_index = data.get("question_index", 0)
    answers = list(data.get("answers", []))

    # Формат callback_data: ans:<тест>:<номер вопроса>:<вариант>
    parts = callback.data.split(":")
    if (
        test_key is None
        or len(parts) != 4
        or parts[1] != test_key
        or parts[2] != str(question_index)
    ):
        # Нажата кнопка из уже отвеченного вопроса (например, продублированное сообщение)
        await callback.answer("Этот вопрос уже пройден 👌")
        return

    answers.append(parts[3])
    questions = TEST_QUESTIONS[test_key]
    next_index = question_index + 1

    if next_index < len(questions):
        await state.update_data(question_index=next_index, answers=answers)
        await callback.message.edit_text(
            _question_text(test_key, next_index),
            reply_markup=_question_reply_markup(test_key, next_index),
        )
        await callback.answer()
        return

    # Тест завершён: сохраняем результат и показываем итог
    await state.clear()
    result_text, payload = RESULT_BUILDERS[test_key](answers)
    tg_user = callback.from_user
    save_test_result(tg_user.id, test_key, payload)
    user = get_user(tg_user.id)

    await callback.message.edit_text(result_text, reply_markup=test_actions_kb(user))
    await callback.message.answer(progress_text(user), reply_markup=main_menu_kb(user))
    await callback.answer("✅ Тест завершён!")


def _question_text(test_key: str, question_index: int) -> str:
    questions = TEST_QUESTIONS[test_key]
    question = questions[question_index]
    lines = [f"❓ <b>Вопрос {question_index + 1} из {len(questions)}</b>\n"]
    stem = TEST_STEMS.get(test_key)
    if stem:
        lines.append(stem + "\n")
    lines.append(question["text"])
    return "\n".join(lines)


def _question_reply_markup(test_key: str, question_index: int):
    question = TEST_QUESTIONS[test_key][question_index]
    return question_kb(
        test_key,
        question_index,
        _question_options(test_key, question),
    )
