import os, re, logging, random
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ===== НАСТРОЙКИ ЧЕРЕЗ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ =====
TOKEN = os.getenv("BOT_TOKEN")                              # токен бота из переменных окружения
ADMIN_USERNAME = (os.getenv("ADMIN_USERNAME") or "pravda_smm").lower()  # ник админа без @
# при первом сообщении от этого ника мы автоматически привяжем numeric ID
ADMIN_USER_ID = None

# ===== ЛОГИ =====
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ===== ХРАНИЛКИ (в памяти) =====
participants = {}      # user_id -> {"name": ..., "username": ..., "phone": ..., "wish": ...}
user_state = {}        # user_id -> "await_contact" | "await_wish" | "done"
pending_admin_msgs = []  # очередь сообщений админу, пока не привязали его ID
PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s()]{6,})")

# ===== СЛУЖЕБНОЕ =====
async def maybe_bind_admin(update: Update):
    """Если пишет @ADMIN_USERNAME — запоминаем его numeric ID."""
    global ADMIN_USER_ID
    u = update.effective_user
    if u and u.username and u.username.lower() == ADMIN_USERNAME:
        if ADMIN_USER_ID != u.id:
            ADMIN_USER_ID = u.id
            logging.info(f"Админ привязан: @{ADMIN_USERNAME} -> {ADMIN_USER_ID}")
            try:
                await update.get_bot().send_message(ADMIN_USER_ID, "✅ Админ подтверждён.")
            except Exception:
                pass

async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str):
    if ADMIN_USER_ID:
        try:
            await context.bot.send_message(ADMIN_USER_ID, text)
        except Exception as e:
            logging.warning(f"Не удалось отправить админу: {e}")
    else:
        pending_admin_msgs.append(text)

async def flush_admin_queue(context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_USER_ID and pending_admin_msgs:
        for msg in pending_admin_msgs[:]:
            try:
                await context.bot.send_message(ADMIN_USER_ID, msg)
                pending_admin_msgs.remove(msg)
            except Exception as e:
                logging.warning(f"Не удалось доставить отложенное админу: {e}")
                break

def is_admin(update: Update) -> bool:
    return ADMIN_USER_ID and update.effective_user and update.effective_user.id == ADMIN_USER_ID

# ===== ПОЛЬЗОВАТЕЛЬСКИЕ ШАГИ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await maybe_bind_admin(update)
    await flush_admin_queue(context)

    uid = update.effective_user.id
    user_state[uid] = "await_contact"

    await update.message.reply_text(
        "Приветствую тебя, сотрудник одного из трёх центров!\n\n"
        "*Я — Тайный Санта для ЦЕНТРОВЫХ.*\n"
        "Как ты уже и сам догадался, этот бот создан специально для сотрудников ЦУР, СЦ (общественно-политический блок) и МЦУ.\n\n"
        "Чтобы принять участие в игре — нажми на кнопку ниже.",
        parse_mode="Markdown",
    )

    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("Поделись своим контактом в tg", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        "Нажми на кнопку ниже, чтобы поделиться своим контактом.\n"
        "Если кнопка не сработала (Telegram Desktop) — *введи номер вручную* в ответном сообщении.",
        reply_markup=kb, parse_mode="Markdown"
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await maybe_bind_admin(update); await flush_admin_queue(context)

    u = update.effective_user
    uid = u.id
    c = update.message.contact

    participants.setdefault(uid, {})
    participants[uid]["name"] = u.first_name or u.full_name or "Участник"
    participants[uid]["username"] = f"@{u.username}" if u.username else ""
    participants[uid]["phone"] = c.phone_number
    user_state[uid] = "await_wish"

    await notify_admin(context,
        f"✅ Новый участник\nID: {uid}\nИмя: {participants[uid]['name']}\n"
        f"Ник: {participants[uid]['username']}\nТелефон: {c.phone_number}"
    )

    await update.message.reply_text(
        "Отлично! Остался ещё один маленький этап и ты в игре.\n"
        "Напиши свои пожелания к подарку и отправь их мне сюда в сообщении.\n\n"
        "Честно-честно, я никому не расскажу. Знать будет только твой тайный санта после жеребьёвки.",
        reply_markup=ReplyKeyboardRemove()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await maybe_bind_admin(update); await flush_admin_queue(context)

    u = update.effective_user
    uid = u.id
    text = update.message.text.strip()

    participants.setdefault(uid, {"name": u.first_name or u.full_name or "Участник",
                                  "username": f"@{u.username}" if u.username else ""})
    state = user_state.get(uid, "await_contact")

    # 1) ждём контакт — принимаем номер текстом (для Desktop)
    if state == "await_contact":
        m = PHONE_RE.search(text)
        if m:
            participants[uid]["phone"] = m.group(0)
            user_state[uid] = "await_wish"

            await notify_admin(context,
                f"✅ Новый участник (текст)\nID: {uid}\nИмя: {participants[uid]['name']}\n"
                f"Ник: {participants[uid]['username']}\nТелефон: {participants[uid]['phone']}"
            )

            await update.message.reply_text(
                "Отлично! Остался ещё один маленький этап и ты в игре.\n"
                "Напиши свои пожелания к подарку и отправь их мне сюда в сообщении.\n\n"
                "Честно-честно, я никому не расскажу. Знать будет только твой тайный санта после жеребьёвки.",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            kb = ReplyKeyboardMarkup(
                [[KeyboardButton("Поделись своим контактом в tg", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True
            )
            await update.message.reply_text(
                "Мне нужен номер телефона. Нажми кнопку ниже *или* отправь номер сообщением "
                "(например: +7 900 000-00-00).",
                reply_markup=kb, parse_mode="Markdown"
            )
        return

    # 2) ждём пожелание
    if state == "await_wish":
        participants[uid]["wish"] = text
        user_state[uid] = "done"

        await notify_admin(context,
            f"🎁 Пожелание\nID: {uid}\nИмя: {participants[uid]['name']}\n"
            f"Ник: {participants[uid]['username']}\nТелефон: {participants[uid]['phone']}\nПожелание: {text}"
        )

        await update.message.reply_text(
            "Поздравляю! Теперь ты участвуешь в игре.\n"
            "2 декабря пройдёт жеребьёвка и ты узнаешь имя и пожелания того, для кого будешь тайным сантой."
        )
        return

    # 3) уже зарегистрирован — разрешим обновлять пожелание
    if state == "done":
        participants[uid]["wish"] = text
        await notify_admin(context,
            f"✏️ Пожелание обновлено\nID: {uid}\nИмя: {participants[uid]['name']}\nНовое пожелание: {text}"
        )
        await update.message.reply_text("Пожелание обновлено. Спасибо!")

# ===== АДМИН-КОМАНДЫ =====
async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.message.reply_text("Команда только для администратора.")
    if not participants:
        return await update.message.reply_text("Список пуст.")
    lines = []
    for uid, info in participants.items():
        lines.append(
            f"ID: {uid} | {info.get('name','')} {info.get('username','')}\n"
            f"Тел: {info.get('phone','—')} | Пожелание: {'да' if info.get('wish') else 'нет'}"
        )
    await update.message.reply_text("Участники:\n\n" + "\n\n".join(lines))

async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.message.reply_text("Команда только для администратора.")
    if not context.args:
        return await update.message.reply_text("Укажи ID участника: /remove 123456789")
    try:
        uid = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("ID должен быть числом.")
    if uid in participants:
        participants.pop(uid, None)
        user_state.pop(uid, None)
        await update.message.reply_text(f"Удалён участник ID {uid}.")
    else:
        await update.message.reply_text("Такого ID нет в списке.")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.message.reply_text("Команда только для администратора.")
    participants.clear()
    user_state.clear()
    await update.message.reply_text("База очищена. ✨")

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.message.reply_text("Команда только для администратора.")

    ready = [(uid, info) for uid, info in participants.items()
             if info.get("phone") and info.get("wish")]
    if len(ready) < 2:
        return await update.message.reply_text("Нужно минимум 2 участника с телефоном и пожеланием.")

    random.shuffle(ready)
    for i in range(len(ready)):
        giver_id, _ = ready[i]
        receiver_id, receiver = ready[(i + 1) % len(ready)]
        try:
            await context.bot.send_message(
                giver_id,
                "Вот человек, которому ты будешь тайным сантой. Удачи!\n\n"
                f"Имя: {receiver.get('name','Участник')}\n"
                f"Пожелание: {receiver.get('wish','(не указано)')}"
            )
        except Exception as e:
            logging.warning(f"Не удалось отправить участнику {giver_id}: {e}")

    await update.message.reply_text("Готово! Сообщения участникам отправлены.")

# ===== ЗАПУСК =====
def main():
    if not TOKEN:
        raise RuntimeError("Переменная окружения BOT_TOKEN не задана.")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("remove", remove_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("draw", draw))

    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()
