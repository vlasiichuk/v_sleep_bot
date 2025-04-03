# -*- coding: utf-8 -*-

from aiogram import Bot, Dispatcher, types
import logging
import sqlite3
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram import F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from aiogram.filters import CommandStart
import os


API_TOKEN = os.getenv("API_TOKEN")

logging.basicConfig(level=logging.INFO)

# 1. Створення об'єкта Bot
bot = Bot(token=API_TOKEN)

# 2. Створення об'єкта MemoryStorage для FSM
storage = MemoryStorage()

# 3. Створення Dispatcher з правильними параметрами
dp = Dispatcher(storage=storage)

# Мапінг ID на імена
user_mapping = {
    385386930: "Таня",
    314376802: "Вова",
    519282184: "Мирослава"
}

# Створення таблиці для збереження даних
def create_connection():
    conn = sqlite3.connect('sleep_data.db')
    return conn

# Функція для створення кнопок
def create_buttons(current_state, user_id):
    if current_state == "sleeping":
        return ReplyKeyboardMarkup(
            keyboard=[[
                KeyboardButton(text="🌞 Прокинувся")],
                [KeyboardButton(text="📜 Історія")]
            ],
            resize_keyboard=True
        )
    elif current_state == "awake":
        return ReplyKeyboardMarkup(
            keyboard=[[
                KeyboardButton(text="🌙 Заснув")],
                [KeyboardButton(text="📜 Історія")]
            ],
            resize_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[[
                KeyboardButton(text="🌙 Заснув")],
                [KeyboardButton(text="📜 Історія")]
            ],
            resize_keyboard=True
        )

def create_table():
    conn = create_connection()
    cursor = conn.cursor()

    # Створення таблиці для користувачів (якщо ще не існує)
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    ''')

    # Створення таблиці для запису логів сну (якщо ще не існує)
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS sleep_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            state TEXT,
            timestamp TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    conn.commit()
    conn.close()


# Функція для реєстрації користувача
async def register_user(user_id, bot, message):
    conn = create_connection()
    cursor = conn.cursor()

    # Перевірка чи є користувач в базі
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user_exists = cursor.fetchone()

    if user_exists:
        # Якщо користувач вже існує, виводимо повідомлення
        # logging.info(f"Користувач з ID {user_id} вже зареєстрований.")
        await message.answer("Ви вже зареєстровані в системі.")
    else:
        # Якщо користувач не знайдений, то додаємо його
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        # logging.info(f"Користувач з ID {user_id} успішно зареєстрований.")
        await message.answer("Вітаємо! Ви успішно зареєстровані.")

    conn.close()

# Перевірка ID при старті
@dp.message(CommandStart())  
async def start(message: types.Message):
    if message.from_user.id not in user_mapping:
        await message.answer("Це приватний бот. Нема чого тут лазити")
        return

    create_table()  # Створення таблиць
    await register_user(message.from_user.id, bot, message)  # Реєстрація користувача

    user_id = message.from_user.id
    username = user_mapping.get(user_id, "Користувач")

    conn = create_connection()
    cursor = conn.cursor()

    # Перевіряємо останній стан користувача
    cursor.execute("SELECT state FROM sleep_log ORDER BY timestamp DESC LIMIT 1")
    last_state = cursor.fetchone()

    if last_state and last_state[0] == "sleeping":
        markup = create_buttons("sleeping", user_id)
    else:
        markup = create_buttons(None, user_id)

    await message.answer(f"Привіт, {username}! Я бот для моніторингу сну вашої дитини. Використовуйте кнопки для фіксації стану.",
                         reply_markup=markup)

    conn.close()

# Функція для отримання всіх користувачів з бази даних
def get_all_users():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

# Функція для надсилання повідомлення всім користувачам
async def notify_users(bot: Bot, message_text: str, exclude_user_id: int):
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    # Ім'я користувача, який створив подію
    initiator_name = user_mapping.get(exclude_user_id, "Користувач")

    for user in users:
        user_id = user[0]
        if user_id != exclude_user_id:
            try:
                # Отримуємо останній стан саме цього користувача
                cursor.execute("""
                    SELECT state FROM sleep_log 
                    
                    ORDER BY timestamp DESC LIMIT 1
                """)
                last_state = cursor.fetchone()
    
                if last_state and last_state[0] == "sleeping":
                    markup = create_buttons("sleeping", user_id)
                else:
                    markup = create_buttons("awake", user_id)
    
                # Надсилаємо повідомлення з кнопками
                await bot.send_message(user_id, f"{initiator_name} {message_text}", reply_markup=markup)
    
            except:
                pass  # Просто ігноруємо помилки

    conn.close()

# Обробка команди "Заснув"
@dp.message(F.text == "🌙 Заснув")
async def sleeping(message: types.Message):
    user_id = message.from_user.id
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")

    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT state, timestamp FROM sleep_log 
        
        ORDER BY timestamp DESC LIMIT 1
    """)
    last_entry = cursor.fetchone()

    cursor.execute(
        "INSERT INTO sleep_log (user_id, state, timestamp) VALUES (?, ?, ?)",
        (user_id, 'sleeping', timestamp_str)
    )
    conn.commit()
    conn.close()

    duration_str = ""
    if last_entry:
        last_state, last_timestamp = last_entry
        last_time = datetime.strptime(last_timestamp, "%Y-%m-%d %H:%M:%S.%f")
        duration = timestamp - last_time
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes = remainder // 60

        if hours > 0:
            duration_str = f" після {hours}г {minutes:02}хв активності"
        else:
            duration_str = f" після {minutes}хв активності"

    #logging.info(f"User {user_id} selected 'Заснув' at {timestamp}")

    await notify_users(bot, f"зафіксував, що дитина заснула{duration_str}.", user_id)
    await message.answer(f"Ви зафіксували, що дитина заснула{duration_str}.", reply_markup=create_buttons("sleeping", user_id))


# Обробка команди "Прокинувся"
@dp.message(F.text == "🌞 Прокинувся")
async def awake(message: types.Message):
    user_id = message.from_user.id
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")

    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT state, timestamp FROM sleep_log 
        
        ORDER BY timestamp DESC LIMIT 1
    """)
    last_entry = cursor.fetchone()

    cursor.execute(
        "INSERT INTO sleep_log (user_id, state, timestamp) VALUES (?, ?, ?)",
        (user_id, 'awake', timestamp_str)
    )
    conn.commit()
    conn.close()

    duration_str = ""
    if last_entry:
        last_state, last_timestamp = last_entry
        last_time = datetime.strptime(last_timestamp, "%Y-%m-%d %H:%M:%S.%f")
        duration = timestamp - last_time
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes = remainder // 60

        if hours > 0:
            duration_str = f" після {hours}г {minutes:02}хв сну"
        else:
            duration_str = f" після {minutes}хв сну"

    #logging.info(f"User {user_id} selected 'Прокинувся' at {timestamp}")

    await notify_users(bot, f"зафіксував, що дитина прокинулась{duration_str}.", user_id)
    await message.answer(f"Ви зафіксували, що дитина прокинулась{duration_str}.", reply_markup=create_buttons("awake", user_id))

# Обробка команди "Історія"
@dp.message(F.text == "📜 Історія")
async def show_history(message: types.Message):
    user_id = message.from_user.id
   
    create_table()
    conn = create_connection()
    cursor = conn.cursor()

    # Отримуємо останні 10 записів
    cursor.execute("SELECT user_id, state, timestamp FROM sleep_log ORDER BY timestamp DESC LIMIT 10")
    history = cursor.fetchall()

    # Перевіряємо останній стан користувача
    cursor.execute("SELECT state FROM sleep_log ORDER BY timestamp DESC LIMIT 1")
    last_state = cursor.fetchone()

    if last_state and last_state[0] == "sleeping":
        markup = create_buttons("sleeping", user_id)
    else:
        markup = create_buttons(None, user_id)

    conn.close()

    if history:
        history_message = "Останні 10 записів:\n"
        history_message += "```\n"  # Початок monospace-блоку
        history_message += "| Час         | Тривалість | Стан       | Користувач     |\n"
        history_message += "|-------------|------------|------------|----------|\n"

        # Перетворюємо історію в список словників
        formatted_history = []
        for user_id_entry, state, timestamp in history:
            formatted_history.append({
                "user_id": user_id_entry,
                "state": state,
                "timestamp": datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
            })

        for i, entry in enumerate(formatted_history):
            current_time = entry["timestamp"]
            username = user_mapping.get(entry["user_id"], "Користувач")
            state_display = "прокинувся" if entry["state"] == 'awake' else "заснув"
            adjusted_time = current_time + timedelta(hours=3)
            formatted_time = adjusted_time.strftime("%d.%m %H:%M")

            # Вираховуємо тривалість до наступного запису
            if i + 1 < len(formatted_history):
                next_time = formatted_history[i + 1]["timestamp"]
                duration = current_time - next_time
                hours, remainder = divmod(int(duration.total_seconds()), 3600)
                minutes = remainder // 60
                duration_str = f"{hours}г {minutes:02}хв"
            else:
                duration_str = "—"

            history_message += f"| {formatted_time:<11} | {duration_str:<10} | {state_display:<10} | {username:<8} |\n"

        history_message += "```"
    else:
        history_message = "Немає записів."

    history_message += f"\nКоманду виконано користувачем з ID: {user_id}"

    #logging.info(f"User {user_id} requested history")

    await message.answer(history_message, reply_markup=markup, parse_mode="Markdown")

# Початок роботи з ботом
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
