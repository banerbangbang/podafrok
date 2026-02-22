"""
Главный файл бота
Запуск и обработка всех сообщений
Теперь: обязательная подписка на канал!
"""

import logging
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
    """
    Проверяет, подписан ли пользователь на обязательный канал
    """
    try:
        # Получаем статус участника канала
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        
        # Статусы, которые считаются подпиской
        if member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            return False
    except Exception as e:
        # Если канал недоступен или бот не админ, логируем ошибку
        logger.error(f"Ошибка проверки подписки для {user_id}: {e}")
        # В случае ошибки лучше пропустить (чтобы бот работал)
        return True

async def subscription_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Декоратор для проверки подписки перед каждым действием
    Возвращает True если есть подписка, False если нет
    """
    user_id = update.effective_user.id
    
    # Проверяем подписку
    is_subscribed = await check_subscription(user_id, context)
    
    if not is_subscribed:
        # Отправляем сообщение о необходимости подписки
        await update.message.reply_text(
            SUBSCRIPTION_REQUIRED_TEXT.format(channel=REQUIRED_CHANNEL),
            parse_mode='HTML'
        )
        return False
    
    return True

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

async def check_active_request_and_notify(user_id, update: Update) -> bool:
    """
    Проверяет, есть ли у пользователя активная заявка
    Если есть - отправляет сообщение и возвращает True
    Если нет - возвращает False
    """
    has_active, request_type = has_active_request(user_id)
    
    if has_active:
        # Определяем какой тип заявки для красивого вывода
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
    """
    Обработчик команды /start
    Проверяет подписку, реферальный параметр и показывает главное меню
    """
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
    
    # Обновляем username (на случай, если поменял)
    if db_user.get("username") != username:
        update_user(user_id, {"username": username})
    
    # Проверяем реферальный параметр
    args = context.args
    if args and args[0].startswith('ref_'):
        inviter_username = extract_username_from_link(args[0])
        if inviter_username and inviter_username != username:
            # Добавляем реферала
            added = add_referral(inviter_username, user_id)
            if added:
                await update.message.reply_text(
                    "🤝 Вы пришли по ссылке друга!\n"
                    "Дождитесь выполнения его условий или подайте свою заявку!"
                )
    
    # Отправляем приветствие с главным меню
    await update.message.reply_text(
        START_TEXT,
        reply_markup=get_main_keyboard()
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /status - показывает прогресс рефералов и статус заявки
    """
    user_id = update.effective_user.id
    
    # Проверяем подписку
    if not await subscription_required(update, context):
        return
    
    db_user = get_user(user_id)
    
    referrals_count = db_user["referrals"]["count"]
    
    # Проверяем активные заявки
    has_active, request_type = has_active_request(user_id)
    
    if has_active:
        active_text = f"✅ Есть (тип: {'⭐️ Звезды' if request_type == 'stars' else '🎁 Premium'})"
    else:
        active_text = "❌ Нет активных заявок"
    
    status_text = f"""
📊 <b>Ваш статус</b>

👥 Приглашено друзей: {referrals_count} из 2

<b>Активная заявка:</b>
{active_text}

<b>Реферальная ссылка:</b>
{format_referral_link(context.bot.username, db_user["username"])}
    """
    
    await update.message.reply_text(status_text, parse_mode='HTML')

async def dell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда для админа: /dell ID_заявки
    Удаляет активную заявку (после выдачи подарка)
    """
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔️ Эта команда только для администратора!")
        return
    
    # Проверяем аргументы
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /dell ID_заявки\n"
            "Пример: /dell stars_5408585719_1708700000"
        )
        return
    
    request_id = context.args[0]
    
    # Ищем заявку
    target_user_id, request_data = get_request_by_id(request_id)
    
    if not target_user_id:
        await update.message.reply_text("❌ Заявка с таким ID не найдена!")
        return
    
    # Удаляем активную заявку
    request_type = request_data["type"]
    remove_active_request(target_user_id, request_type)
    
    await update.message.reply_text(
        f"✅ Заявка {request_id} удалена!\n"
        f"Пользователь может создать новую заявку."
    )
    
    # Уведомляем пользователя
    try:
        await context.bot.send_message(
            target_user_id,
            "✅ Ваша предыдущая заявка обработана. Вы можете создать новую!",
            reply_markup=get_main_keyboard()
        )
    except:
        pass

# ================== ОБРАБОТЧИКИ СООБЩЕНИЙ ==================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает все текстовые сообщения
    """
    user_id = update.effective_user.id
    
    # Проверяем подписку (кроме команды /start)
    if not await subscription_required(update, context):
        return
    
    text = update.message.text
    
    # Главное меню
    if text == "Звезды 🎁":
        await start_stars_request(update, context)
    elif text == "TG Premium ⭐️":
        await start_premium_request(update, context)
    elif text == "О боте ℹ️":
        await update.message.reply_text(ABOUT_TEXT, parse_mode='HTML')
    else:
        # Проверяем, находится ли пользователь в каком-то состоянии
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
                # Неизвестное состояние
                user_states.pop(user_id, None)
                await update.message.reply_text(
                    "Используйте кнопки меню 👆",
                    reply_markup=get_main_keyboard()
                )
        else:
            # Просто игнорируем
            await update.message.reply_text(
                "Используйте кнопки меню 👆",
                reply_markup=get_main_keyboard()
            )

# ================== ЗВЕЗДЫ: ШАГИ ==================

async def start_stars_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Шаг 1: Начало заявки на Звезды
    """
    user_id = update.effective_user.id
    
    # Проверяем, нет ли уже активной заявки (ЛЮБОЙ)
    if await check_active_request_and_notify(user_id, update):
        return
    
    # Запрашиваем количество
    user_states[user_id] = {"action": "waiting_stars_amount"}
    
    await update.message.reply_text(
        f"Сколько звезд вы хотите получить?\n"
        f"(Максимум: {MAX_STARS} звезд. Введите число)"
    )

async def process_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Шаг 2: Обработка количества звезд
    """
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Проверяем, что ввели число
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text("❌ Ошибка! Введите число цифрами.")
        return
    
    # Проверяем диапазон
    if amount <= 0 or amount > MAX_STARS:
        await update.message.reply_text(
            f"❌ Введите число от 1 до {MAX_STARS}."
        )
        return
    
    # Сохраняем количество
    context.user_data['stars_amount'] = amount
    
    # Переходим к следующему шагу
    user_states[user_id] = {"action": "waiting_stars_username"}
    
    await update.message.reply_text(
        "Хорошо. Теперь укажите ваш @username в Telegram:"
    )

async def process_stars_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Шаг 3: Обработка username
    """
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Добавляем @ если нет
    if not text.startswith('@'):
        text = '@' + text
    
    context.user_data['stars_username'] = text
    
    # Переходим к следующему шагу
    user_states[user_id] = {"action": "waiting_stars_datetime"}
    
    await update.message.reply_text(
        "В какое время вам отправить подарок?\n"
        "Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 23.02.2026 18:00"
    )

async def process_stars_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Шаг 4: Обработка даты и времени + финальная отправка админу
    """
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Проверяем дату
    is_valid, result = validate_datetime(text)
    
    if not is_valid:
        await update.message.reply_text(result)
        return
    
    # Получаем сохраненные данные
    amount = context.user_data.get('stars_amount')
    stars_username = context.user_data.get('stars_username')
    
    # Данные заявки
    request_data = {
        "amount": amount,
        "username": stars_username,
        "datetime": text,
        "user_username": update.effective_user.username or f"id{user_id}"
    }
    
    # Сохраняем в БД
    request_id = add_active_request(user_id, "stars", request_data)
    
    # Очищаем состояние
    user_states.pop(user_id, None)
    context.user_data.clear()
    
    # Отправляем пользователю подтверждение
    await update.message.reply_text(
        "✅ Ваша заявка на Звезды отправлена на рассмотрение!\n"
        "Ожидайте ответа администратора.",
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
    """
    
    await context.bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=get_accept_request_keyboard(request_id)
    )

# ================== PREMIUM: ШАГИ ==================

async def start_premium_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Шаг 1: Начало заявки на Premium (выбор срока)
    """
    user_id = update.effective_user.id
    
    # Проверяем, нет ли уже активной заявки (ЛЮБОЙ)
    if await check_active_request_and_notify(user_id, update):
        return
    
    # Отправляем инлайн-кнопки для выбора срока
    await update.message.reply_text(
        "На сколько месяцев хотите получить Premium?",
        reply_markup=get_premium_duration_keyboard()
    )

async def process_premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка выбора срока Premium (нажатие на инлайн-кнопку)
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Еще раз проверяем активную заявку
    has_active, _ = has_active_request(user_id)
    if has_active:
        await query.edit_message_text(
            "❌ У вас уже есть активная заявка!\n"
            "Дождитесь ее обработки."
        )
        return
    
    # Получаем выбранный срок
    months = int(query.data.split('_')[1])
    
    # Находим название срока
    duration_name = None
    for name, value in PREMIUM_OPTIONS.items():
        if value == months:
            duration_name = name
            break
    
    # Сохраняем в context.user_data
    context.user_data['premium_duration'] = months
    context.user_data['premium_duration_name'] = duration_name
    
    # Переходим к следующему шагу
    user_states[user_id] = {"action": "waiting_premium_datetime"}
    
    # Редактируем сообщение с кнопками
    await query.edit_message_text(
        f"Выбрано: {duration_name}\n\n"
        "Когда хотите получить подарок?\n"
        "Напишите дату и время в формате: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 23.02.2026 18:00"
    )

async def process_premium_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Шаг 2: Обработка даты и времени для Premium
    """
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Проверяем дату
    is_valid, result = validate_datetime(text)
    
    if not is_valid:
        await update.message.reply_text(result)
        return
    
    # Еще раз проверяем активную заявку
    has_active, _ = has_active_request(user_id)
    if has_active:
        await update.message.reply_text(
            "❌ У вас уже есть активная заявка!\n"
            "Дождитесь ее обработки.",
            reply_markup=get_main_keyboard()
        )
        user_states.pop(user_id, None)
        context.user_data.clear()
        return
    
    # Получаем сохраненные данные
    months = context.user_data.get('premium_duration')
    duration_name = context.user_data.get('premium_duration_name')
    
    # Данные заявки
    request_data = {
        "duration": months,
        "duration_name": duration_name,
        "datetime": text,
        "user_username": update.effective_user.username or f"id{user_id}"
    }
    
    # Сохраняем в БД
    request_id = add_active_request(user_id, "premium", request_data)
    
    # Очищаем состояние
    user_states.pop(user_id, None)
    context.user_data.clear()
    
    # Отправляем пользователю подтверждение
    await update.message.reply_text(
        "✅ Ваша заявка на Premium отправлена на рассмотрение!\n"
        "Ожидайте ответа администратора.",
        reply_markup=get_main_keyboard()
    )
    
    # Отправляем админу
    admin_text = f"""
🔔 НОВАЯ ЗАЯВКА (PREMIUM)
От: @{request_data['user_username']}
Срок: {duration_name}
Время получения: {text}

ID заявки: {request_id}
    """
    
    await context.bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=get_accept_request_keyboard(request_id)
    )

# ================== ОБРАБОТКА КНОПКИ "ПРИНЯТЬ" ==================

async def handle_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка нажатия на кнопку "Принять заявку" (для админа)
    """
    query = update.callback_query
    await query.answer()
    
    # Проверяем, что нажал админ
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔️ Эта кнопка только для администратора!")
        return
    
    # Получаем ID заявки
    request_id = query.data.replace('accept_', '')
    
    # Ищем заявку
    user_id, request_data = get_request_by_id(request_id)
    
    if not user_id:
        await query.edit_message_text("❌ Заявка не найдена!")
        return
    
    # Получаем данные пользователя для реферальной ссылки
    db_user = get_user(user_id)
    bot_username = context.bot.username
    
    # Формируем реферальную ссылку
    referral_link = format_referral_link(bot_username, db_user["username"])
    
    # Отправляем пользователю условия
    try:
        if request_data["type"] == "stars":
            conditions = STARS_CONDITIONS.format(referral_link=referral_link)
        else:
            conditions = PREMIUM_CONDITIONS.format(referral_link=referral_link)
        
        await context.bot.send_message(
            user_id,
            conditions,
            parse_mode='HTML'
        )
        
        # Уведомляем админа
        await query.edit_message_text(
            f"✅ Условия отправлены пользователю!\n"
            f"Заявка: {request_id}"
        )
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ Не удалось отправить условия пользователю!\n"
            f"Ошибка: {e}\n\n"
            f"Заявка: {request_id}"
        )

# ================== ЗАПУСК БОТА ==================

def main():
    """
    Главная функция запуска бота
    """
    # Инициализируем БД
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("dell", dell_command))
    
    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Регистрируем обработчики инлайн-кнопок
    application.add_handler(CallbackQueryHandler(process_premium_callback, pattern="^premium_"))
    application.add_handler(CallbackQueryHandler(handle_accept_callback, pattern="^accept_"))
    
    # Запускаем бота
    print("Бот запущен! Нажмите Ctrl+C для остановки.")
    print(f"Обязательная подписка на {REQUIRED_CHANNEL}")
    print("Условия: 2 реферала, убрали канал из условий")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
