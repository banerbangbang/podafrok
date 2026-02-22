"""
Вспомогательные функции для бота
"""

from datetime import datetime
import re

def validate_datetime(date_string):
    """
    Проверяет, соответствует ли строка формату ДД.ММ.ГГГГ ЧЧ:ММ
    Возвращает (True, datetime_object) если всё ок
    Или (False, сообщение_об_ошибке) если есть проблема
    """
    # Проверяем формат регулярным выражением
    pattern = r'^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})$'
    match = re.match(pattern, date_string)
    
    if not match:
        return False, "Неверный формат. Используйте: ДД.ММ.ГГГГ ЧЧ:ММ (например: 23.02.2026 18:00)"
    
    day, month, year, hour, minute = map(int, match.groups())
    
    # Проверяем, что дата существует
    try:
        date_obj = datetime(year, month, day, hour, minute)
    except ValueError:
        return False, "❌ Такой даты не существует! Проверьте числа."
    
    # Проверяем, что дата не в прошлом
    if date_obj < datetime.now():
        return False, "❌ Нельзя выбрать дату в прошлом! Выберите будущую дату."
    
    return True, date_obj

def generate_request_id(user_id, request_type):
    """
    Генерирует уникальный ID для заявки
    Формат: тип_юзер id_таймштамп
    Например: stars_5408585719_1708700000
    """
    timestamp = int(datetime.now().timestamp())
    return f"{request_type}_{user_id}_{timestamp}"

def extract_username_from_link(start_param):
    """
    Извлекает username из реферального параметра
    ?start=ref_username -> username
    """
    if start_param and start_param.startswith('ref_'):
        return start_param[4:]  # убираем 'ref_'
    return None

def format_referral_link(bot_username, username):
    """
    Создает реферальную ссылку для пользователя
    """
    return f"https://t.me/{bot_username}?start=ref_{username}"