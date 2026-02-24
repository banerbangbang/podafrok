"""
Вспомогательные функции
"""

from datetime import datetime
import re

def validate_datetime(date_string):
    pattern = r'^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})$'
    match = re.match(pattern, date_string)
    
    if not match:
        return False, "Неверный формат. Используйте: ДД.ММ.ГГГГ ЧЧ:ММ"
    
    day, month, year, hour, minute = map(int, match.groups())
    
    try:
        date_obj = datetime(year, month, day, hour, minute)
    except ValueError:
        return False, "❌ Такой даты не существует!"
    
    if date_obj < datetime.now():
        return False, "❌ Нельзя выбрать дату в прошлом!"
    
    return True, date_obj

def generate_request_id(user_id, request_type):
    timestamp = int(datetime.now().timestamp())
    return f"{request_type}_{user_id}_{timestamp}"

def extract_username_from_link(start_param):
    if start_param and start_param.startswith('ref_'):
        return start_param[4:]
    return None

def format_referral_link(bot_username, username):
    return f"https://t.me/{bot_username}?start=ref_{username}"
