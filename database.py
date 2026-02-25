"""
Работа с базой данных (файл user.json)
Хранит всех пользователей, их заявки и рефералов
"""

import json
import os
from datetime import datetime

# Имя файла с данными
DB_FILE = "user.json"

def init_db():
    """
    Создает файл user.json, если его нет
    """
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2, ensure_ascii=False)

def load_db():
    """
    Загружает данные из файла
    """
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(data):
    """
    Сохраняет данные в файл
    """
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user(user_id):
    """
    Получает данные конкретного пользователя
    """
    data = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in data:
        data[user_id_str] = {
            "username": None,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "referrals": {
                "count": 0,
                "referred_users": []
            },
            "invited_by": None,
            "active_requests": {
                "stars": None,
                "premium": None
            },
            "requests_history": []
        }
        save_db(data)
    
    return data[user_id_str]

def update_user(user_id, updates):
    """
    Обновляет данные пользователя
    """
    data = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in data:
        data[user_id_str] = {}
    
    for key, value in updates.items():
        if isinstance(value, dict) and key in data[user_id_str] and isinstance(data[user_id_str][key], dict):
            data[user_id_str][key].update(value)
        else:
            data[user_id_str][key] = value
    
    save_db(data)
    return data[user_id_str]

def has_active_request(user_id):
    """
    Проверяет, есть ли у пользователя активная заявка
    Возвращает True/False
    """
    data = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in data:
        return False
    
    # Прямая проверка данных
    if data[user_id_str]["active_requests"]["stars"] is not None:
        return True
    if data[user_id_str]["active_requests"]["premium"] is not None:
        return True
    
    return False

def get_active_request_type(user_id):
    """
    Возвращает тип активной заявки или None
    """
    data = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in data:
        return None
    
    if data[user_id_str]["active_requests"]["stars"] is not None:
        return "stars"
    if data[user_id_str]["active_requests"]["premium"] is not None:
        return "premium"
    
    return None

def add_referral(inviter_username, new_user_id):
    """
    Добавляет реферала пригласившему
    """
    data = load_db()
    new_user_id_str = str(new_user_id)
    
    inviter_id = None
    for uid, uinfo in data.items():
        if uinfo.get("username") == inviter_username:
            inviter_id = uid
            break
    
    if not inviter_id:
        return False
    
    if new_user_id_str in data[inviter_id]["referrals"]["referred_users"]:
        return False
    
    data[inviter_id]["referrals"]["count"] += 1
    data[inviter_id]["referrals"]["referred_users"].append(new_user_id_str)
    
    if new_user_id_str in data:
        data[new_user_id_str]["invited_by"] = inviter_id
    
    save_db(data)
    return True

def add_active_request(user_id, request_type, request_data):
    """
    Добавляет активную заявку пользователю
    ТОЛЬКО ОДНА ЗАЯВКА - НАВСЕГДА!
    """
    # Загружаем данные напрямую
    data = load_db()
    user_id_str = str(user_id)
    
    # Если пользователя нет - создаем
    if user_id_str not in data:
        data[user_id_str] = {
            "username": request_data.get("user_username"),
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "referrals": {"count": 0, "referred_users": []},
            "invited_by": None,
            "active_requests": {"stars": None, "premium": None},
            "requests_history": []
        }
    
    # ЖЕСТОЧАЙШАЯ ПРОВЕРКА - смотрим оба типа
    if data[user_id_str]["active_requests"]["stars"] is not None:
        print(f"❌ БЛОКИРОВКА: У пользователя {user_id} уже есть заявка на звезды")
        return False
    
    if data[user_id_str]["active_requests"]["premium"] is not None:
        print(f"❌ БЛОКИРОВКА: У пользователя {user_id} уже есть заявка на premium")
        return False
    
    # Проверка через историю (на случай если active_requests сбросился)
    for req in data[user_id_str]["requests_history"]:
        if req["status"] == "pending":
            print(f"❌ БЛОКИРОВКА: Найдена pending заявка в истории {req['id']}")
            return False
    
    # Генерируем ID заявки
    from utils import generate_request_id
    request_id = generate_request_id(user_id, request_type)
    
    # Данные заявки
    full_request = {
        "id": request_id,
        "type": request_type,
        "user_id": user_id,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": request_data
    }
    
    # Сохраняем
    data[user_id_str]["active_requests"][request_type] = request_id
    data[user_id_str]["requests_history"].append(full_request)
    
    save_db(data)
    print(f"✅ Заявка {request_id} создана")
    return request_id

def remove_active_request(user_id, request_type):
    """
    Удаляет активную заявку (после выдачи)
    """
    data = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in data:
        return None
    
    request_id = data[user_id_str]["active_requests"][request_type]
    data[user_id_str]["active_requests"][request_type] = None
    
    for req in data[user_id_str]["requests_history"]:
        if req["id"] == request_id:
            req["status"] = "completed"
            req["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    
    save_db(data)
    print(f"✅ Заявка {request_id} удалена")
    return request_id

def get_request_by_id(request_id):
    """
    Находит заявку по её ID
    """
    data = load_db()
    
    for user_id_str, user_info in data.items():
        for req in user_info["requests_history"]:
            if req["id"] == request_id:
                return int(user_id_str), req
    
    return None, None
