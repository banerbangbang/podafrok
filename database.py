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
    """Получает данные конкретного пользователя"""
    data = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in data:
        # Новый пользователь
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
    """
    Проверяет, есть ли у пользователя активная заявка (любого типа)
    ВОЗВРАЩАЕТ ТОЛЬКО True/False
    """
    user = get_user(user_id)
    
    # Проверяем оба типа
    if user["active_requests"]["stars"] is not None:
        return True
    if user["active_requests"]["premium"] is not None:
        return True
    
    return False

def get_active_request_type(user_id):
    """Возвращает тип активной заявки или None"""
    user = get_user(user_id)
    
    if user["active_requests"]["stars"] is not None:
        return "stars"
    if user["active_requests"]["premium"] is not None:
        return "premium"
    
    return None

def add_referral(inviter_username, new_user_id):
    """Добавляет реферала пригласившему"""
    data = load_db()
    new_user_id_str = str(new_user_id)
    
    # Ищем пригласившего по username
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
    Возвращает ID заявки или False если уже есть
    """
    user_data = load_db()
    user_id_str = str(user_id)
    
    # === ТРОЙНАЯ ПРОВЕРКА ===
    
    # 1. Проверка через get_user
    user = get_user(user_id)
    
    # 2. Проверяем заявку этого же типа
    if user["active_requests"][request_type] is not None:
        print(f"❌ Заявка типа {request_type} уже существует")
        return False
    
    # 3. Проверяем ЛЮБУЮ активную заявку
    if user["active_requests"]["stars"] is not None or user["active_requests"]["premium"] is not None:
        print(f"❌ У пользователя {user_id} уже есть активная заявка")
        return False
    
    # 4. ФИНАЛЬНАЯ проверка - смотрим напрямую в данные
    if user_id_str in user_data:
        if user_data[user_id_str]["active_requests"]["stars"] is not None:
            print(f"❌ Прямая проверка: есть заявка stars")
            return False
        if user_data[user_id_str]["active_requests"]["premium"] is not None:
            print(f"❌ Прямая проверка: есть заявка premium")
            return False
    
    # Если все проверки пройдены - создаем заявку
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
    
    # Сохраняем
    user_data[user_id_str]["active_requests"][request_type] = request_id
    user_data[user_id_str]["requests_history"].append(full_request)
    
    save_db(user_data)
    print(f"✅ Заявка {request_id} создана")
    return request_id

def remove_active_request(user_id, request_type):
    """Удаляет активную заявку"""
    user_data = load_db()
    user_id_str = str(user_id)
    
    request_id = user_data[user_id_str]["active_requests"][request_type]
    user_data[user_id_str]["active_requests"][request_type] = None
    
    # В истории отмечаем как завершенную
    for req in user_data[user_id_str]["requests_history"]:
        if req["id"] == request_id:
            req["status"] = "completed"
            req["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    
    save_db(user_data)
    print(f"✅ Заявка {request_id} удалена")
    return request_id

def get_request_by_id(request_id):
    """Находит заявку по её ID"""
    data = load_db()
    
    for user_id_str, user_info in data.items():
        for req in user_info["requests_history"]:
            if req["id"] == request_id:
                return int(user_id_str), req
    
    return None, None

def cleanup_old_requests(hours=12):
    """Удаляет старые заявки"""
    data = load_db()
    now = datetime.now()
    cleaned = 0
    
    for user_id_str, user_info in data.items():
        for req in user_info["requests_history"]:
            if req["status"] == "pending":
                created = datetime.strptime(req["created_at"], "%Y-%m-%d %H:%M:%S")
                delta = (now - created).total_seconds()
                if delta > hours * 3600:
                    req["status"] = "expired"
                    if req["id"] == user_info["active_requests"][req["type"]]:
                        user_info["active_requests"][req["type"]] = None
                    cleaned += 1
    
    if cleaned > 0:
        save_db(data)
    
    return cleaned
