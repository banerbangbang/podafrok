"""
Главный файл бота
Запуск и обработка всех сообщений
Автопринятие через 60 секунд (надежная версия)
"""

import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# Наши модули
from config import (
    BOT_TOKEN, ADMIN_ID, MAX_STARS, ABOUT_TEXT, START_TEXT,
    STARS_CONDITIONS, PREMIUM_CONDITIONS, PREMIUM_OPTIONS,
    REQUIRED_CHANNEL, REQUIRED_CHANNEL_ID, SUBSCRIPTION_REQUIRED_TEXT
)
from keyboards import (
    get_main_keyboard,
    get_premium_duration_keyboard,
    get_accept_request_keyboard
)
from database import (
    init_db,
    load_db,
    save_db,
    get_user,
    update_user,
    add_referral,
    add_active_request,
    remove_active_request,
    get_request_by_id,
    has_active_request,
    can_create_request
)
from utils import (
    validate_datetime,
    format_referral_link,
    extract_username_from_link
)

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния пользователей
user_states = {}

# ================== ПРОВЕРКА ПОДПИСКИ ==================

async def check_subscription(user_id, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, подписан ли пользователь на обязательный канал"""
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки подписки для {user_id}: {e}")
        return True

async def subscription_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверка подписки перед действием"""
    user_id = update.effective_user.id
    is_subscribed = await check_subscription(user_id, context)
    
    if not is_subscribed:
        await update.message.reply_text(
            SUBSCRIPTION_REQUIRED_TEXT.format(channel=REQUIRED_CHANNEL),
            parse_mode='HTML'
        )
        return False
    
    return True

# ================== ПРОВЕРКА АВТОПРИНЯТИЯ ==================

async def check_auto_accept(context: ContextTypes.DEFAULT_TYPE):
    """
    Проверяет все активные заявки и принимает те, которым больше 60 секунд
    Запускается каждые 10 секунд
    """
    try:
        data = load_db()
        now = datetime.now()
        accepted = 0
        to_remove = []  # Список заявок для удаления
        
        for user_id_str, user_data in data.items():
            user_id = int(user_id_str)
            
            # Проверяем заявки на звезды
            if user_data["active_requests"]["stars"]:
                request_id = user_data["active_requests"]["stars"]
                found = False
                
                for req in user_data["requests_history"]:
                    if req["id"] == request_id:
                        found = True
                        if req["status"] == "pending":
                            created = datetime.strptime(req["created_at"], "%Y-%m-%d %H:%M:%S")
                            delta = (now - created).total_seconds()
                            
                            if delta >= 60:
                                logger.info(f"⚡ Автопринятие заявки {request_id}")
                                
                                # ПРОВЕРЯЕМ, ЧТО ПОЛЬЗОВАТЕЛЬ ЕЩЕ СУЩЕСТВУЕТ
                                try:
                                    await context.bot.get_chat(user_id)
                                    
                                    db_user = get_user(user_id)
                                    referral_link = format_referral_link(context.bot.username, db_user["username"])
                                    
                                    if req["type"] == "stars":
                                        conditions = STARS_CONDITIONS.format(referral_link=referral_link)
                                    else:
                                        conditions = PREMIUM_CONDITIONS.format(referral_link=referral_link)
                                    
                                    await context.bot.send_message(user_id, conditions, parse_mode='HTML')
                                    
                                    req["status"] = "accepted"
                                    user_data["active_requests"]["stars"] = None
                                    
                                    await context.bot.send_message(
                                        ADMIN_ID,
                                        f"✅ Заявка {request_id} автоматически принята через 60 секунд!"
                                    )
                                    accepted += 1
                                except Exception as e:
                                    # Пользователь заблокировал бота или удалил аккаунт
                                    logger.warning(f"Пользователь {user_id} недоступен, удаляем заявку {request_id}")
                                    to_remove.append((user_id_str, "stars", request_id))
                        break
                
                if not found:
                    # Заявка есть в active_requests, но нет в истории - очищаем
                    to_remove.append((user_id_str, "stars", request_id))
            
            # Проверяем заявки на premium
            if user_data["active_requests"]["premium"]:
                request_id = user_data["active_requests"]["premium"]
                found = False
                
                for req in user_data["requests_history"]:
                    if req["id"] == request_id:
                        found = True
                        if req["status"] == "pending":
                            created = datetime.strptime(req["created_at"], "%Y-%m-%d %H:%M:%S")
                            delta = (now - created).total_seconds()
                            
                            if delta >= 60:
                                logger.info(f"⚡ Автопринятие заявки {request_id}")
                                
                                # ПРОВЕРЯЕМ, ЧТО ПОЛЬЗОВАТЕЛЬ ЕЩЕ СУЩЕСТВУЕТ
                                try:
                                    await context.bot.get_chat(user_id)
                                    
                                    db_user = get_user(user_id)
                                    referral_link = format_referral_link(context.bot.username, db_user["username"])
                                    
                                    if req["type"] == "stars":
                                        conditions = STARS_CONDITIONS.format(referral_link=referral_link)
                                    else:
                                        conditions = PREMIUM_CONDITIONS.format(referral_link=referral_link)
                                    
                                    await context.bot.send_message(user_id, conditions, parse_mode='HTML')
                                    
                                    req["status"] = "accepted"
                                    user_data["active_requests"]["premium"] = None
                                    
                                    await context.bot.send_message(
                                        ADMIN_ID,
                                        f"✅ Заявка {request_id} автоматически принята через 60 секунд!"
                                    )
                                    accepted += 1
                                except Exception as e:
                                    # Пользователь заблокировал бота или удалил аккаунт
                                    logger.warning(f"Пользователь {user_id} недоступен, удаляем заявку {request_id}")
                                    to_remove.append((user_id_str, "premium", request_id))
                        break
                
                if not found:
                    # Заявка есть в active_requests, но нет в истории - очищаем
                    to_remove.append((user_id_str, "premium", request_id))
        
        # Удаляем проблемные заявки
        for user_id_str, req_type, req_id in to_remove:
            if user_id_str in data:
                data[user_id_str]["active_requests"][req_type] = None
                logger.info(f"🗑 Удалена битая заявка {req_id}")
        
        if accepted > 0 or to_remove:
            save_db(data)
            logger.info(f"✅ Автоматически принято: {accepted}, удалено битых: {len(to_remove)}")
            
    except Exception as e:
        logger.error(f"Ошибка при проверке автопринятия: {e}")

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

async def check_active_request_and_notify(user_id, update: Update) -> bool:
    """Проверяет, есть ли у пользователя активная заявка"""
    has_active, request_type = has_active_request(user_id)
    
    if has_active:
        type_display = "⭐️ Звезды" if request_type == "stars" else "🎁 Premium"
        
        await update.message.reply_text(
            f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
            f"У вас уже есть активная заявка на {type_display}!\n"
            f"Можно выбрать только <b>ОДИН</b> подарок.\n"
            f"Дождитесь обработки текущей заявки.\n\n"
            f"Используйте /status чтобы проверить статус.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
        return True
    
    return False

# ================== КОМАНДЫ ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    username = user.username or f"user_{user_id}"
    
    # Проверяем подписку
    if not await check_subscription(user_id, context):
        await update.message.reply_text(
            SUBSCRIPTION_REQUIRED_TEXT.format(channel=REQUIRED_CHANNEL),
            parse_mode='HTML'
        )
        return
    
    # Получаем или создаем пользователя в БД
    db_user = get_user(user_id)
    
    # Обновляем username
    if db_user.get("username") != username:
        update_user(user_id, {"username": username})
    
    # Проверяем реферальный параметр
    args = context.args
    if args and args[0].startswith('ref_'):
        inviter_username = extract_username_from_link(args[0])
        if inviter_username and inviter_username != username:
            added = add_referral(inviter_username, user_id)
            if added:
                await update.message.reply_text(
                    "🤝 Вы пришли по ссылке друга!\n"
                    "Дождитесь выполнения его условий или подайте свою заявку!"
                )
    
    # Отправляем приветствие
    await update.message.reply_text(
        START_TEXT,
        reply_markup=get_main_keyboard()
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    user_id = update.effective_user.id
    
    if not await subscription_required(update, context):
        return
    
    db_user = get_user(user_id)
    referrals_count = db_user["referrals"]["count"]
    
    has_active, request_type = has_active_request(user_id)
    
    if has_active:
        active_text = f"✅ Есть (тип: {'⭐️ Звезды' if request_type == 'stars' else '🎁 Premium'})"
    else:
        active_text = "❌ Нет активных заявок"
    
    # Проверяем, получал ли пользователь уже подарок
    has_gift = False
    for req in db_user["requests_history"]:
        if req["status"] in ["accepted", "completed"]:
            has_gift = True
            break
    
    gift_text = "✅ Получал" if has_gift else "❌ Не получал"
    
    status_text = f"""
📊 <b>Ваш статус</b>

👥 Приглашено друзей: {referrals_count} из 2
🎁 Подарок: {gift_text}

<b>Активная заявка:</b>
{active_text}

<b>Реферальная ссылка:</b>
{format_referral_link(context.bot.username, db_user["username"])}
    """
    
    await update.message.reply_text(status_text, parse_mode='HTML')

async def dell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для админа: /dell ID_заявки"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔️ Эта команда только для администратора!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /dell ID_заявки\n"
            "Пример: /dell stars_5408585719_1708700000"
        )
        return
    
    request_id = context.args[0]
    
    target_user_id, request_data = get_request_by_id(request_id)
    
    if not target_user_id:
        await update.message.reply_text("❌ Заявка с таким ID не найдена!")
        return
    
    request_type = request_data["type"]
    remove_active_request(target_user_id, request_type)
    
    await update.message.reply_text(
        f"✅ Заявка {request_id} удалена!\n"
        f"Пользователь может создать новую заявку."
    )
    
    try:
        await context.bot.send_message(
            target_user_id,
            "✅ Ваша предыдущая заявка обработана. Вы можете создать новую!",
            reply_markup=get_main_keyboard()
        )
    except:
        pass

# ================== ОБРАБОТЧИКИ СООБЩЕНИЙ ==================

async def handle_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки Звезды"""
    if not await subscription_required(update, context):
        return
    await start_stars_request(update, context)

async def handle_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки TG Premium"""
    if not await subscription_required(update, context):
        return
    await start_premium_request(update, context)

async def handle_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки О боте"""
    if not await subscription_required(update, context):
        return
    await update.message.reply_text(ABOUT_TEXT, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все текстовые сообщения (для состояний)"""
    user_id = update.effective_user.id
    
    if not await subscription_required(update, context):
        return
    
    if user_id in user_states:
        state = user_states[user_id]
        
        if state["action"] == "waiting_stars_amount":
            await process_stars_amount(update, context)
        elif state["action"] == "waiting_stars_username":
            await process_stars_username(update, context)
        elif state["action"] == "waiting_stars_datetime":
            await process_stars_datetime(update, context)
        elif state["action"] == "waiting_premium_datetime":
            await process_premium_datetime(update, context)
        else:
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "Используйте кнопки меню 👆",
                reply_markup=get_main_keyboard()
            )
    else:
        # Если нет состояния, но пользователь что-то написал
        await update.message.reply_text(
            "Используйте кнопки меню 👆",
            reply_markup=get_main_keyboard()
        )

# ================== ЗВЕЗДЫ: ШАГИ ==================

async def start_stars_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 1: Начало заявки на Звезды"""
    user_id = update.effective_user.id
    
    # Проверяем, может ли пользователь создать заявку
    can_create, reason = can_create_request(user_id)
    if not can_create:
        await update.message.reply_text(
            f"⚠️ {reason}\n\n"
            f"Каждый пользователь может получить только ОДИН подарок!",
            reply_markup=get_main_keyboard()
        )
        return
    
    user_states[user_id] = {"action": "waiting_stars_amount"}
    
    await update.message.reply_text(
        f"Сколько звезд вы хотите получить?\n"
        f"(Максимум: {MAX_STARS} звезд. Введите число)"
    )

async def process_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 2: Обработка количества звезд"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text("❌ Ошибка! Введите число цифрами.")
        return
    
    if amount <= 0 or amount > MAX_STARS:
        await update.message.reply_text(
            f"❌ Введите число от 1 до {MAX_STARS}."
        )
        return
    
    context.user_data['stars_amount'] = amount
    user_states[user_id] = {"action": "waiting_stars_username"}
    
    await update.message.reply_text(
        "Хорошо. Теперь укажите ваш @username в Telegram:"
    )

async def process_stars_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 3: Обработка username"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not text.startswith('@'):
        text = '@' + text
    
    context.user_data['stars_username'] = text
    user_states[user_id] = {"action": "waiting_stars_datetime"}
    
    await update.message.reply_text(
        "В какое время вам отправить подарок?\n"
        "Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 23.02.2026 18:00"
    )

async def process_stars_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 4: Обработка даты и времени + отправка админу"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    is_valid, result = validate_datetime(text)
    
    if not is_valid:
        await update.message.reply_text(result)
        return
    
    amount = context.user_data.get('stars_amount')
    stars_username = context.user_data.get('stars_username')
    
    request_data = {
        "amount": amount,
        "username": stars_username,
        "datetime": text,
        "user_username": update.effective_user.username or f"id{user_id}"
    }
    
    # Пытаемся создать заявку
    success, request_result = add_active_request(user_id, "stars", request_data)
    
    if not success:
        await update.message.reply_text(
            f"❌ {request_result}",
            reply_markup=get_main_keyboard()
        )
        user_states.pop(user_id, None)
        context.user_data.clear()
        return
    
    request_id = request_result
    
    user_states.pop(user_id, None)
    context.user_data.clear()
    
    await update.message.reply_text(
        "✅ Ваша заявка на Звезды отправлена на рассмотрение!\n"
        "Ожидайте ответа администратора (автоматически в течение 1 минуты).",
        reply_markup=get_main_keyboard()
    )
    
    # Отправляем админу
    admin_text = f"""
🔔 НОВАЯ ЗАЯВКА (ЗВЕЗДЫ)
От: @{request_data['user_username']}
Количество: {amount} ⭐️
Username для отправки: {stars_username}
Время получения: {text}

ID заявки: {request_id}

⏱ Автопринятие через 60 секунд
    """
    
    await context.bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=get_accept_request_keyboard(request_id)
    )

# ================== PREMIUM: ШАГИ ==================

async def start_premium_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 1: Начало заявки на Premium"""
    user_id = update.effective_user.id
    
    # Проверяем, может ли пользователь создать заявку
    can_create, reason = can_create_request(user_id)
    if not can_create:
        await update.message.reply_text(
            f"⚠️ {reason}\n\n"
            f"Каждый пользователь может получить только ОДИН подарок!",
            reply_markup=get_main_keyboard()
        )
        return
    
    await update.message.reply_text(
        "На сколько месяцев хотите получить Premium?",
        reply_markup=get_premium_duration_keyboard()
    )

async def process_premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора срока Premium"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, может ли пользователь создать заявку
    can_create, reason = can_create_request(user_id)
    if not can_create:
        await query.edit_message_text(
            f"⚠️ {reason}"
        )
        return
    
    months = int(query.data.split('_')[1])
    
    duration_name = None
    for name, value in PREMIUM_OPTIONS.items():
        if value == months:
            duration_name = name
            break
    
    context.user_data['premium_duration'] = months
    context.user_data['premium_duration_name'] = duration_name
    
    user_states[user_id] = {"action": "waiting_premium_datetime"}
    
    await query.edit_message_text(
        f"Выбрано: {duration_name}\n\n"
        "Когда хотите получить подарок?\n"
        "Напишите дату и время в формате: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 23.02.2026 18:00"
    )

async def process_premium_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 2: Обработка даты и времени для Premium"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    is_valid, result = validate_datetime(text)
    
    if not is_valid:
        await update.message.reply_text(result)
        return
    
    months = context.user_data.get('premium_duration')
    duration_name = context.user_data.get('premium_duration_name')
    
    request_data = {
        "duration": months,
        "duration_name": duration_name,
        "datetime": text,
        "user_username": update.effective_user.username or f"id{user_id}"
    }
    
    # Пытаемся создать заявку
    success, request_result = add_active_request(user_id, "premium", request_data)
    
    if not success:
        await update.message.reply_text(
            f"❌ {request_result}",
            reply_markup=get_main_keyboard()
        )
        user_states.pop(user_id, None)
        context.user_data.clear()
        return
    
    request_id = request_result
    
    user_states.pop(user_id, None)
    context.user_data.clear()
    
    await update.message.reply_text(
        "✅ Ваша заявка на Premium отправлена на рассмотрение!\n"
        "Ожидайте ответа администратора (автоматически в течение 1 минуты).",
        reply_markup=get_main_keyboard()
    )
    
    # Отправляем админу
    admin_text = f"""
🔔 НОВАЯ ЗАЯВКА (PREMIUM)
От: @{request_data['user_username']}
Срок: {duration_name}
Время получения: {text}

ID заявки: {request_id}

⏱ Автопринятие через 60 секунд
    """
    
    await context.bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=get_accept_request_keyboard(request_id)
    )

# ================== ОБРАБОТКА КНОПКИ "ПРИНЯТЬ" ==================

async def handle_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия на кнопку "Принять заявку" (для админа)"""
    query = update.callback_query
    await query.answer()
    
    # Проверяем, что нажал админ
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔️ Эта кнопка только для администратора!")
        return
    
    # Получаем ID заявки
    request_id = query.data.replace('accept_', '')
    logger.info(f"👆 Ручное принятие заявки {request_id}")
    
    # Ищем заявку
    user_id, request_data = get_request_by_id(request_id)
    
    if not user_id:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    
    # Проверяем, существует ли пользователь
    try:
        await context.bot.get_chat(user_id)
    except Exception as e:
        await query.edit_message_text(f"❌ Пользователь не найден или заблокировал бота! Заявка будет удалена.")
        # Удаляем заявку
        remove_active_request(user_id, request_data["type"])
        return
    
    # Проверяем, что заявка еще в статусе pending
    if request_data["status"] != "pending":
        await query.edit_message_text(f"❌ Заявка уже {request_data['status']}!")
        return
    
    # Получаем данные пользователя
    db_user = get_user(user_id)
    bot_username = context.bot.username
    referral_link = format_referral_link(bot_username, db_user["username"])
    
    # Отправляем условия
    try:
        if request_data["type"] == "stars":
            conditions = STARS_CONDITIONS.format(referral_link=referral_link)
        else:
            conditions = PREMIUM_CONDITIONS.format(referral_link=referral_link)
        
        await context.bot.send_message(user_id, conditions, parse_mode='HTML')
        
        # Обновляем статус в БД
        data = load_db()
        for req in data[str(user_id)]["requests_history"]:
            if req["id"] == request_id:
                req["status"] = "accepted"
                break
        data[str(user_id)]["active_requests"][request_data["type"]] = None
        save_db(data)
        
        await query.edit_message_text(f"✅ Заявка {request_id} принята вручную!")
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}")

# ================== ЗАПУСК БОТА ==================

def main():
    """Главная функция запуска бота"""
    # Инициализируем БД
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("dell", dell_command))
    
    # Регистрируем обработчики для кнопок меню (с разными вариантами текста)
    application.add_handler(MessageHandler(
        filters.Text(["Звезды 🎁", "Звезды"]), 
        handle_stars
    ))
    application.add_handler(MessageHandler(
        filters.Text(["TG Premium ⭐️", "TG Premium"]), 
        handle_premium
    ))
    application.add_handler(MessageHandler(
        filters.Text(["О боте ℹ️", "О боте"]), 
        handle_about
    ))
    
    # Регистрируем обработчик для всех остальных текстовых сообщений (состояния)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Регистрируем обработчики инлайн-кнопок
    application.add_handler(CallbackQueryHandler(process_premium_callback, pattern="^premium_"))
    application.add_handler(CallbackQueryHandler(handle_accept_callback, pattern="^accept_"))
    
    # Запускаем проверку автопринятия каждые 10 секунд
    application.job_queue.run_repeating(check_auto_accept, interval=10, first=5)
    
    # Запускаем бота
    print("=" * 50)
    print("Бот ЗАПУЩЕН!")
    print(f"Обязательная подписка на {REQUIRED_CHANNEL}")
    print("Условия: 2 реферала")
    print("⏱ Автопринятие заявок через 60 секунд (проверка каждые 10 сек)")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
