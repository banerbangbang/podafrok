"""
Работа с базой данных (файл user.json)
Хранит всех пользователей, их заявки и рефералов
"""

import json
import os
from datetime import datetime

DB_FILE = "user.json"

def init_db():
    """Создает файл user.json, если его нет"""
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2, ensure_ascii=False)

def load_db():
    """Загружает данные из файла"""
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(data):
    """Сохраняет данные в файл"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user(user_id):
    """Получает данные пользователя"""
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
    """Обновляет данные пользователя"""
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
    """Проверяет, есть ли у пользователя активная заявка"""
    user = get_user(user_id)
    
    if user["active_requests"]["stars"]:
        return True, "stars"
    elif user["active_requests"]["premium"]:
        return True, "premium"
    else:
        return False, None

def add_referral(inviter_username, new_user_id):
    """Добавляет реферала"""
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
    """Добавляет активную заявку пользователю"""
    user = get_user(user_id)
    
    # Проверяем только заявку этого же типа
    if user["active_requests"][request_type] is not None:
        return False
    
    from utils import generate_request_id
    request_id = generate_request_id(user_id, request_type)
    
    full_request = {
        "id": request_id,
        "type": request_type,
        "user_id": user_id,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": request_data
    }
    
    user_data = load_db()
    user_id_str = str(user_id)
    user_data[user_id_str]["active_requests"][request_type] = request_id
    user_data[user_id_str]["requests_history"].append(full_request)
    
    save_db(user_data)
    return request_id

def remove_active_request(user_id, request_type):
    """Удаляет активную заявку"""
    user_data = load_db()
    user_id_str = str(user_id)
    
    request_id = user_data[user_id_str]["active_requests"][request_type]
    user_data[user_id_str]["active_requests"][request_type] = None
    
    for req in user_data[user_id_str]["requests_history"]:
        if req["id"] == request_id:
            req["status"] = "completed"
            req["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    
    save_db(user_data)
    return request_id

def get_request_by_id(request_id):
    """Находит заявку по ID"""
    data = load_db()
    
    for user_id_str, user_info in data.items():
        for req in user_info["requests_history"]:
            if req["id"] == request_id:
                return int(user_id_str), req
    
    return None, None
