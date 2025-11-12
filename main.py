import os
import json
import random
import logging
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==== НАСТРОЙКИ ====
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "pravda_smm")

USERS_FILE = "users.json"
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ==== ХРАНЕНИЕ ДАННЫХ ====
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==== КОМАНДА /start ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    name = user.full_name

    text = (
        "Приветствую тебя, сотрудник одного из трёх центров!\n\n"
        "*Я — Тайный Санта для ЦЕНТРОВЫХ.* 🎅\n"
        "Как ты уже и сам догадался, этот бот был создан специально для сотрудников "
        "ЦУР, СЦ (общественно-политический блок) и МЦУ.\n\n"
        "Чтобы принять участие в игре — нажми на кнопку ниже 👇"
    )

    keyboard = [[KeyboardButton("📱 Поделись своим контактом в tg", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ==== ОБРАБОТКА КОНТАКТА ====
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user_id = str(update.message.from_user.id)

    users = load_users()
    users[user_id] = {
        "name": contact.first_name or update.message.from_user.full_name,
        "phone": contact.phone_number,
    }
    save_users(users)

    await update.message.reply_text(
        "Отлично! Остался ещё один маленький этап, и ты в игре 🎁\n\n"
        "Напиши свои *пожелания к подарку* и отправь их мне сюда сообщением.\n\n"
        "_Честно-честно, я никому не расскажу. Знать будет только твой тайный Санта после жеребьёвки._",
        parse_mode="Markdown",
        reply_markup=None,
    )

# ==== ОБРАБОТКА ПОЖЕЛАНИЯ ====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text

    users = load_users()
    if user_id in users and "wish" not in users[user_id]:
        users[user_id]["wish"] = text
        save_users(users)

        await update.message.reply_text(
            "🎉 Поздравляю! Теперь ты участвуешь в игре.\n\n"
            "2 декабря пройдет жеребьёвка, и ты узнаешь имя и пожелания того, "
            "для кого будешь Тайным Сантой. Удачи!"
        )
    else:
        await update.message.reply_text("Чтобы начать сначала, нажми /start")

# ==== АДМИН-КОМАНДЫ ====
async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username != ADMIN_USERNAME:
        return await update.message.reply_text("Нет доступа 🚫")

    users = load_users()
    text = "📋 Участники:\n\n" + "\n\n".join(
        [f"{u['name']} — {u.get('phone', '—')}\n🎁 {u.get('wish', '—')}" for u in users.values()]
    )
    await update.message.reply_text(text or "Пока пусто.")

async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username != ADMIN_USERNAME:
        return await update.message.reply_text("Нет доступа 🚫")
    if not context.args:
        return await update.message.reply_text("Используй: /remove <user_id>")

    users = load_users()
    user_id = context.args[0]
    if user_id in users:
        del users[user_id]
        save_users(users)
        await update.message.reply_text(f"Пользователь {user_id} удалён ✅")
    else:
        await update.message.reply_text("Такого пользователя нет.")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username != ADMIN_USERNAME:
        return await update.message.reply_text("Нет доступа 🚫")

    save_users({})
    await update.message.reply_text("База участников сброшена 🗑️")

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username != ADMIN_USERNAME:
        return await update.message.reply_text("Нет доступа 🚫")

    users = load_users()
    ready = list(users.items())
    if len(ready) < 2:
        return await update.message.reply_text("Недостаточно участников для жеребьёвки 😅")

    random.shuffle(ready)
    for i in range(len(ready)):
        giver_id, giver = ready[i]
        receiver_id, receiver = ready[(i + 1) % len(ready)]
        try:
            await context.bot.send_message(
                giver_id,
                f"🎅 Вот человек, которому ты будешь Тайным Сантой!\n\n"
                f"Имя: *{receiver.get('name', '—')}*\n"
                f"Пожелание: _{receiver.get('wish', 'не указано')}_",
                parse_mode="Markdown",
            )
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение {giver_id}: {e}")

    await update.message.reply_text("✅ Сообщения участникам отправлены!")

# ==== ЗАПУСК ЧЕРЕЗ WEBHOOK ====
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

    public_url = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL")
    if not public_url:
        raise RuntimeError("Не найден WEBHOOK_URL/RENDER_EXTERNAL_URL. Render создаёт его автоматически.")

    port = int(os.getenv("PORT", "10000"))

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TOKEN,
        webhook_url=f"{public_url}/{TOKEN}",
    )

if __name__ == "__main__":
    main()
