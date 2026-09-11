import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = "@aryanmohamadi1"
ADMIN_ID = int(os.environ["ADMIN_ID"])

DB_NAME = "story.db"

ADD_TITLE, ADD_TEXT = range(2)


def db():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            text TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_pages():
    conn = db()
    rows = conn.execute(
        "SELECT id, title, text FROM pages ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


def add_page(title, text):
    conn = db()
    conn.execute(
        "INSERT INTO pages (title, text) VALUES (?, ?)",
        (title, text)
    )
    conn.commit()
    conn.close()


def delete_last_page():
    conn = db()
    conn.execute(
        "DELETE FROM pages WHERE id = (SELECT MAX(id) FROM pages)"
    )
    conn.commit()
    conn.close()


async def is_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


def page_keyboard(index, total):
    buttons = []

    if index > 0:
        buttons.append(
            InlineKeyboardButton(
                "◀️ صفحه قبل",
                callback_data=f"page:{index-1}"
            )
        )

    if index < total - 1:
        buttons.append(
            InlineKeyboardButton(
                "صفحه بعد ▶️",
                callback_data=f"page:{index+1}"
            )
        )

    return InlineKeyboardMarkup([buttons]) if buttons else None


def make_page(index):
    pages = get_pages()

    if not pages:
        return "📖 هنوز داستانی اضافه نشده.", None

    _, title, text = pages[index]

    message = (
        f"📖 <b>{title}</b>\n\n"
        f"{text}\n\n"
        f"<i>قسمت {index+1} از {len(pages)}</i>"
    )

    return message, page_keyboard(index, len(pages))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update.effective_user.id, context):
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📢 عضویت در کانال",
                    url="https://t.me/aryanmohamadi1"
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ بررسی عضویت",
                    callback_data="check_member"
                )
            ]
        ])

        await update.message.reply_text(
            "برای خواندن داستان ابتدا عضو کانال شوید 👇",
            reply_markup=keyboard
        )
        return

    message, keyboard = make_page(0)

    await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def check_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await is_member(query.from_user.id, context):
        await query.answer(
            "❌ هنوز عضو کانال نیستید!",
            show_alert=True
        )
        return

    message, keyboard = make_page(0)

    await query.edit_message_text(
        message,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def change_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    index = int(query.data.split(":")[1])
    pages = get_pages()

    if not pages or index >= len(pages):
        return

    message, keyboard = make_page(index)

    await query.edit_message_text(
        message,
        parse_mode="HTML",
        reply_markup=keyboard
    )


def admin_only(update):
    return update.effective_user.id == ADMIN_ID


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_only(update):
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return

    pages = get_pages()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ افزودن قسمت",
                callback_data="admin_add"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 لیست قسمت‌ها",
                callback_data="admin_list"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 حذف آخرین قسمت",
                callback_data="admin_delete"
            )
        ]
    ])

    await update.message.reply_text(
        f"👨‍💻 <b>پنل مدیریت</b>\n\n"
        f"📚 تعداد قسمت‌ها: {len(pages)}",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    await query.message.reply_text(
        "📝 عنوان قسمت را بفرست:"
    )

    return ADD_TITLE


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    context.user_data["title"] = update.message.text

    await update.message.reply_text(
        "📖 حالا متن قسمت را کامل بفرست:"
    )

    return ADD_TEXT


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    title = context.user_data["title"]
    text = update.message.text

    add_page(title, text)

    context.user_data.clear()

    await update.message.reply_text(
        "✅ قسمت داستان اضافه شد!"
    )

    return ConversationHandler.END


async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    pages = get_pages()

    if not pages:
        await query.message.reply_text(
            "📚 هنوز هیچ قسمتی وجود ندارد."
        )
        return

    text = "📚 <b>قسمت‌های داستان:</b>\n\n"

    for i, page in enumerate(pages, 1):
        text += f"{i}. {page[1]}\n"

    await query.message.reply_text(
        text,
        parse_mode="HTML"
    )


async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    pages = get_pages()

    if not pages:
        await query.message.reply_text(
            "❌ قسمتی برای حذف وجود ندارد."
        )
        return

    title = pages[-1][1]
    delete_last_page()

    await query.message.reply_text(
        f"🗑 «{title}» حذف شد."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ لغو شد.")
    return ConversationHandler.END


def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                admin_add,
                pattern="^admin_add$"
            )
        ],
        states={
            ADD_TITLE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_title
                )
            ],
            ADD_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_text
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(conversation)

    app.add_handler(
        CallbackQueryHandler(
            check_member,
            pattern="^check_member$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            change_page,
            pattern="^page:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_list,
            pattern="^admin_list$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_delete,
            pattern="^admin_delete$"
        )
    )

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
