"""
Главный файл бота
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
    has_active_request
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
    """Проверяет подписку на канал"""
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
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
    """Проверяет заявки и принимает через 60 секунд"""
    try:
        data = load_db()
        now = datetime.now()
        accepted = 0
        
        for user_id_str, user_data in data.items():
            user_id = int(user_id_str)
            
            # Проверяем звезды
            if user_data["active_requests"]["stars"]:
                request_id = user_data["active_requests"]["stars"]
                for req in user_data["requests_history"]:
                    if req["id"] == request_id and req["status"] == "pending":
                        created = datetime.strptime(req["created_at"], "%Y-%m-%d %H:%M:%S")
                        delta = (now - created).total_seconds()
                        
                        if delta >= 60:
                            logger.info(f"Автопринятие {request_id}")
                            
                            db_user = get_user(user_id)
                            referral_link = format_referral_link(context.bot.username, db_user["username"])
                            
                            conditions = STARS_CONDITIONS.format(referral_link=referral_link)
                            await context.bot.send_message(user_id, conditions, parse_mode='HTML')
                            
                            req["status"] = "accepted"
                            user_data["active_requests"]["stars"] = None
                            
                            await context.bot.send_message(
                                ADMIN_ID,
                                f"✅ Заявка {request_id} автоматически принята"
                            )
                            accepted += 1
                        break
            
            # Проверяем premium
            if user_data["active_requests"]["premium"]:
                request_id = user_data["active_requests"]["premium"]
                for req in user_data["requests_history"]:
                    if req["id"] == request_id and req["status"] == "pending":
                        created = datetime.strptime(req["created_at"], "%Y-%m-%d %H:%M:%S")
                        delta = (now - created).total_seconds()
                        
                        if delta >= 60:
                            logger.info(f"Автопринятие {request_id}")
                            
                            db_user = get_user(user_id)
                            referral_link = format_referral_link(context.bot.username, db_user["username"])
                            
                            conditions = PREMIUM_CONDITIONS.format(referral_link=referral_link)
                            await context.bot.send_message(user_id, conditions, parse_mode='HTML')
                            
                            req["status"] = "accepted"
                            user_data["active_requests"]["premium"] = None
                            
                            await context.bot.send_message(
                                ADMIN_ID,
                                f"✅ Заявка {request_id} автоматически принята"
                            )
                            accepted += 1
                        break
        
        if accepted > 0:
            save_db(data)
            
    except Exception as e:
        logger.error(f"Ошибка автопринятия: {e}")

# ================== КОМАНДЫ ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start"""
    user = update.effective_user
    user_id = user.id
    username = user.username or f"user_{user_id}"
    
    if not await check_subscription(user_id, context):
        await update.message.reply_text(
            SUBSCRIPTION_REQUIRED_TEXT.format(channel=REQUIRED_CHANNEL),
            parse_mode='HTML'
        )
        return
    
    db_user = get_user(user_id)
    
    if db_user.get("username") != username:
        update_user(user_id, {"username": username})
    
    args = context.args
    if args and args[0].startswith('ref_'):
        inviter_username = extract_username_from_link(args[0])
        if inviter_username and inviter_username != username:
            added = add_referral(inviter_username, user_id)
            if added:
                await update.message.reply_text("🤝 Вы пришли по ссылке друга!")
    
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
        active_text = f"✅ Есть ({'⭐️' if request_type == 'stars' else '🎁'})"
    else:
        active_text = "❌ Нет"
    
    status_text = f"""
📊 <b>Статус</b>

👥 Приглашено: {referrals_count} из 2

<b>Заявка:</b> {active_text}

<b>Ссылка:</b>
{format_referral_link(context.bot.username, db_user["username"])}
    """
    
    await update.message.reply_text(status_text, parse_mode='HTML')

async def dell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для админа /dell"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔️ Только для админа!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ /dell ID_заявки")
        return
    
    request_id = context.args[0]
    target_user_id, request_data = get_request_by_id(request_id)
    
    if not target_user_id:
        await update.message.reply_text("❌ Заявка не найдена")
        return
    
    remove_active_request(target_user_id, request_data["type"])
    await update.message.reply_text(f"✅ Заявка {request_id} удалена")

# ================== ОБРАБОТЧИК СООБЩЕНИЙ ==================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик сообщений"""
    user_id = update.effective_user.id
    
    if not await subscription_required(update, context):
        return
    
    text = update.message.text
    
    if text == "Звезды 🎁":
        await start_stars_request(update, context)
    elif text == "TG Premium ⭐️":
        await start_premium_request(update, context)
    elif text == "О боте ℹ️":
        await update.message.reply_text(ABOUT_TEXT, parse_mode='HTML')
    else:
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
                await update.message.reply_text("Используйте кнопки меню 👆")
        else:
            await update.message.reply_text("Используйте кнопки меню 👆")

# ================== ЗВЕЗДЫ ==================

async def start_stars_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    has_active, _ = has_active_request(user_id)
    if has_active:
        await update.message.reply_text("⚠️ У вас уже есть активная заявка!")
        return
    
    user_states[user_id] = {"action": "waiting_stars_amount"}
    await update.message.reply_text(f"Сколько звезд? (1-{MAX_STARS})")

async def process_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return
    
    if amount <= 0 or amount > MAX_STARS:
        await update.message.reply_text(f"❌ От 1 до {MAX_STARS}")
        return
    
    context.user_data['stars_amount'] = amount
    user_states[user_id] = {"action": "waiting_stars_username"}
    await update.message.reply_text("Ваш @username:")

async def process_stars_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not text.startswith('@'):
        text = '@' + text
    
    context.user_data['stars_username'] = text
    user_states[user_id] = {"action": "waiting_stars_datetime"}
    await update.message.reply_text("Дата и время (ДД.ММ.ГГГГ ЧЧ:ММ):")

async def process_stars_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    request_id = add_active_request(user_id, "stars", request_data)
    
    user_states.pop(user_id, None)
    context.user_data.clear()
    
    await update.message.reply_text(
        "✅ Заявка отправлена! Ожидайте (авто 60 сек)",
        reply_markup=get_main_keyboard()
    )
    
    admin_text = f"""
🔔 НОВАЯ ЗАЯВКА (ЗВЕЗДЫ)
От: @{request_data['user_username']}
Количество: {amount} ⭐️
Username: {stars_username}
Время: {text}
ID: {request_id}
    """
    
    await context.bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=get_accept_request_keyboard(request_id)
    )

# ================== PREMIUM ==================

async def start_premium_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    has_active, _ = has_active_request(user_id)
    if has_active:
        await update.message.reply_text("⚠️ У вас уже есть активная заявка!")
        return
    
    await update.message.reply_text(
        "Срок Premium?",
        reply_markup=get_premium_duration_keyboard()
    )

async def process_premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    has_active, _ = has_active_request(user_id)
    if has_active:
        await query.edit_message_text("❌ Уже есть активная заявка")
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
        f"Выбрано: {duration_name}\n\nДата и время (ДД.ММ.ГГГГ ЧЧ:ММ):"
    )

async def process_premium_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    request_id = add_active_request(user_id, "premium", request_data)
    
    user_states.pop(user_id, None)
    context.user_data.clear()
    
    await update.message.reply_text(
        "✅ Заявка отправлена! Ожидайте (авто 60 сек)",
        reply_markup=get_main_keyboard()
    )
    
    admin_text = f"""
🔔 НОВАЯ ЗАЯВКА (PREMIUM)
От: @{request_data['user_username']}
Срок: {duration_name}
Время: {text}
ID: {request_id}
    """
    
    await context.bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=get_accept_request_keyboard(request_id)
    )

# ================== КНОПКА ПРИНЯТЬ ==================

async def handle_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔️ Только для админа!")
        return
    
    request_id = query.data.replace('accept_', '')
    logger.info(f"Ручное принятие {request_id}")
    
    user_id, request_data = get_request_by_id(request_id)
    
    if not user_id:
        await query.edit_message_text("❌ Заявка не найдена")
        return
    
    db_user = get_user(user_id)
    referral_link = format_referral_link(context.bot.username, db_user["username"])
    
    try:
        if request_data["type"] == "stars":
            conditions = STARS_CONDITIONS.format(referral_link=referral_link)
        else:
            conditions = PREMIUM_CONDITIONS.format(referral_link=referral_link)
        
        await context.bot.send_message(user_id, conditions, parse_mode='HTML')
        
        data = load_db()
        for req in data[str(user_id)]["requests_history"]:
            if req["id"] == request_id:
                req["status"] = "accepted"
                break
        data[str(user_id)]["active_requests"][request_data["type"]] = None
        save_db(data)
        
        await query.edit_message_text(f"✅ Заявка принята!")
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}")

# ================== ЗАПУСК ==================

def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("dell", dell_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(process_premium_callback, pattern="^premium_"))
    application.add_handler(CallbackQueryHandler(handle_accept_callback, pattern="^accept_"))
    
    application.job_queue.run_repeating(check_auto_accept, interval=10, first=5)
    
    print("=" * 50)
    print("БОТ ЗАПУЩЕН!")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
