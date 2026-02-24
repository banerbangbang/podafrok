"""
Клавиатуры для бота
"""

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("Звезды 🎁")],
        [KeyboardButton("TG Premium ⭐️")],
        [KeyboardButton("О боте ℹ️")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_premium_duration_keyboard():
    keyboard = [
        [InlineKeyboardButton("1 месяц", callback_data="premium_1")],
        [InlineKeyboardButton("3 месяца", callback_data="premium_3")],
        [InlineKeyboardButton("12 месяцев", callback_data="premium_12")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_accept_request_keyboard(request_id):
    keyboard = [
        [InlineKeyboardButton("✅ Принять заявку", callback_data=f"accept_{request_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)
