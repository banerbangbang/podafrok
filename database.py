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
    Если пользователя нет, создает базовую структуру
    """
    data = load_db()
    user_id_str = str(user_id)
    
    if user_id_str not in data:
        # Новый пользователь
        data[user_id_str] = {
            "username": None,  # @username
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "referrals": {
                "count": 0,  # сколько уникальных пригласил
                "referred_users": []  # список ID тех, кого пригласил
            },
            "invited_by": None,  # кто пригласил этого пользователя
            "active_requests": {
                "stars": None,  # ID активной заявки на звезды или None
                "premium": None  # ID активной заявки на premium или None
            },
            "requests_history": []  # история всех заявок
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
    
    # Рекурсивно обновляем словарь
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
    Проверяет по статусу в истории, а не только по active_requests
    Возвращает (True, тип) или (False, None)
    """
    user = get_user(user_id)
    
    # Проверяем активные заявки в истории
    for req in user["requests_history"]:
        if req["status"] == "pending":  # Если есть хоть одна pending заявка
            return True, req["type"]
    
    # Если в истории нет pending, но в active_requests что-то есть - очищаем
    data = load_db()
    user_id_str = str(user_id)
    changed = False
    
    if user["active_requests"]["stars"]:
        # Проверяем, есть ли такая заявка в истории со статусом pending
        found = False
        for req in user["requests_history"]:
            if req["id"] == user["active_requests"]["stars"] and req["status"] == "pending":
                found = True
                break
        
        if not found:
            data[user_id_str]["active_requests"]["stars"] = None
            changed = True
    
    if user["active_requests"]["premium"]:
        found = False
        for req in user["requests_history"]:
            if req["id"] == user["active_requests"]["premium"] and req["status"] == "pending":
                found = True
                break
        
        if not found:
            data[user_id_str]["active_requests"]["premium"] = None
            changed = True
    
    if changed:
        save_db(data)
        # Перезагружаем пользователя
        user = get_user(user_id)
    
    # Финальная проверка
    if user["active_requests"]["stars"] or user["active_requests"]["premium"]:
        # Двойная проверка - смотрим тип
        if user["active_requests"]["stars"]:
            return True, "stars"
        else:
            return True, "premium"
    
    return False, None

def can_create_request(user_id):
    """
    Проверяет, может ли пользователь создать новую заявку
    Возвращает (True, None) если можно, или (False, причина) если нельзя
    """
    user = get_user(user_id)
    
    # Проверка 1: Есть ли активная заявка
    has_active, active_type = has_active_request(user_id)
    if has_active:
        return False, f"У вас уже есть активная заявка на {'⭐️ Звезды' if active_type == 'stars' else '🎁 Premium'}"
    
    # Проверка 2: Был ли пользователь уже в боте и получал заявки
    # Если в истории уже есть заявки со статусом accepted/completed - НЕ ДАЕМ СОЗДАВАТЬ НОВЫЕ
    for req in user["requests_history"]:
        if req["status"] in ["accepted", "completed"]:
            return False, "Вы уже получали подарок. Каждый пользователь может получить только один подарок!"
    
    return True, None

def add_active_request(user_id, request_type, request_data):
    """
    Добавляет активную заявку пользователю
    request_type: 'stars' или 'premium'
    request_data: словарь с данными заявки
    """
    user = get_user(user_id)
    
    # Проверяем, можно ли создать заявку
    can_create, reason = can_create_request(user_id)
    if not can_create:
        return False, reason
    
    # Генерируем ID заявки
    from utils import generate_request_id
    request_id = generate_request_id(user_id, request_type)
    
    # Данные заявки
    full_request = {
        "id": request_id,
        "type": request_type,
        "user_id": user_id,
        "status": "pending",  # pending, accepted, completed
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": request_data
    }
    
    # Сохраняем в историю
    user_data = load_db()
    user_id_str = str(user_id)
    user_data[user_id_str]["active_requests"][request_type] = request_id
    user_data[user_id_str]["requests_history"].append(full_request)
    
    save_db(user_data)
    return True, request_id

def remove_active_request(user_id, request_type):
    """
    Удаляет активную заявку (после выдачи или отклонения)
    """
    user_data = load_db()
    user_id_str = str(user_id)
    
    request_id = user_data[user_id_str]["active_requests"][request_type]
    user_data[user_id_str]["active_requests"][request_type] = None
    
    # В истории можно отметить как завершенную
    for req in user_data[user_id_str]["requests_history"]:
        if req["id"] == request_id:
            req["status"] = "completed"
            req["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    
    save_db(user_data)
    return request_id

def get_request_by_id(request_id):
    """
    Находит заявку по её ID (ищет по всем пользователям)
    Возвращает (user_id, request_data) или (None, None)
    """
    data = load_db()
    
    for user_id_str, user_info in data.items():
        for req in user_info["requests_history"]:
            if req["id"] == request_id:
                return int(user_id_str), req
    
    return None, None

def add_referral(inviter_username, new_user_id):
    """
    Добавляет реферала пригласившему
    Возвращает True, если реферал уникальный и добавлен
    """
    data = load_db()
    new_user_id_str = str(new_user_id)
    
    # Ищем пригласившего по username
    inviter_id = None
    for uid, uinfo in data.items():
        if uinfo.get("username") == inviter_username:
            inviter_id = uid
            break
    
    if not inviter_id:
        return False  # пригласивший не найден
    
    # Проверяем, не был ли этот пользователь уже рефералом
    if new_user_id_str in data[inviter_id]["referrals"]["referred_users"]:
        return False  # уже приглашал этого
    
    # Добавляем реферала
    data[inviter_id]["referrals"]["count"] += 1
    data[inviter_id]["referrals"]["referred_users"].append(new_user_id_str)
    
    # Записываем, кто пригласил нового пользователя
    if new_user_id_str in data:
        data[new_user_id_str]["invited_by"] = inviter_id
    
    save_db(data)
    return True
