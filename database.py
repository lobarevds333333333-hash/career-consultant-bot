"""Работа с SQLite: пользователи, результаты тестов, заявки на консультацию."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from config import config
from tests_data import TEST_ORDER

# Ключи результатов в таблице users называются "<ключ теста>_result"
RESULT_COLUMNS = {f"{key}_result" for key in TEST_ORDER}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id       INTEGER PRIMARY KEY,
    username          TEXT,
    full_name         TEXT,
    career_result     TEXT,
    thinking_result   TEXT,
    motivation_result TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     INTEGER NOT NULL,
    name            TEXT NOT NULL,
    preferred_time  TEXT NOT NULL,
    contact_channel TEXT NOT NULL,
    contact         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)


def upsert_user(telegram_id: int, username: str | None, full_name: str | None) -> None:
    """Создаёт запись пользователя или обновляет его данные из Telegram."""
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_id, username, full_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                updated_at = excluded.updated_at
            """,
            (telegram_id, username, full_name, now, now),
        )


def save_test_result(telegram_id: int, test_key: str, payload: dict[str, Any]) -> None:
    """Сохраняет результат теста (JSON) в соответствующую колонку пользователя."""
    column = f"{test_key}_result"
    if column not in RESULT_COLUMNS:
        raise ValueError(f"Неизвестный тест: {test_key!r}")
    now = _now()
    with _connect() as conn:
        # На случай, если пользователь вдруг не проходил /start
        conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, created_at, updated_at) VALUES (?, ?, ?)",
            (telegram_id, now, now),
        )
        conn.execute(
            f"UPDATE users SET {column} = ?, updated_at = ? WHERE telegram_id = ?",
            (json.dumps(payload, ensure_ascii=False), now, telegram_id),
        )


def get_user(telegram_id: int) -> dict[str, Any] | None:
    """Возвращает пользователя с распарсенными результатами тестов (dict | None)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    if row is None:
        return None
    user = dict(row)
    for column in RESULT_COLUMNS:
        raw = user.get(column)
        user[column] = json.loads(raw) if raw else None
    return user


def add_booking(
    telegram_id: int,
    name: str,
    preferred_time: str,
    contact_channel: str,
    contact: str,
) -> int:
    """Сохраняет заявку на консультацию и возвращает её номер."""
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO bookings
                (telegram_id, name, preferred_time, contact_channel, contact, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (telegram_id, name, preferred_time, contact_channel, contact, _now()),
        )
        return int(cursor.lastrowid or 0)


def completed_tests(user: dict[str, Any] | None) -> set[str]:
    """Множество ключей уже пройденных тестов."""
    if not user:
        return set()
    return {key for key in TEST_ORDER if user.get(f"{key}_result") is not None}


def missing_tests(user: dict[str, Any] | None) -> list[str]:
    """Список ключей ещё не пройденных тестов (в порядке TEST_ORDER)."""
    done = completed_tests(user)
    return [key for key in TEST_ORDER if key not in done]
