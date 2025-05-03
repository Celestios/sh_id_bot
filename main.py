import os
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
import hashlib
from base62 import encode, decode
import re

# ─── CONFIG ───────────────────────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_NAME = os.getenv("ADMIN_NAME")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError):
    raise RuntimeError("Invalid or missing ADMIN_ID in environment.")


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def make_main_menu(anon_mode: bool, ):
    button_label_1 = "در حالت ناشناس هستی. خروج؟" if anon_mode else "ورود به حالت ناشناس"
    button_label_2 = "دستور ها و قابلیت ها"
    button_label_3 = "پاکسازی پیام ها"
    buttons = [[InlineKeyboardButton(button_label_1, callback_data="toggle_anon")],
               [InlineKeyboardButton(button_label_2, callback_data="help")],
               [InlineKeyboardButton(button_label_3, callback_data="cleanup")]]
    return InlineKeyboardMarkup(buttons)


def make_response_menu(anon_id: int):
    button_label_1 = f"✏️ درحال پاسخ به {anon_id}هستی "
    button_label_2 = "لغو کردن"
    buttons = [
        [InlineKeyboardButton(button_label_1, callback_data="ignore")],
        [InlineKeyboardButton(button_label_2, callback_data="cancel_send")]
    ]
    return InlineKeyboardMarkup(buttons)


# Helper function to send or update the main menu
async def manage_main_menu(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str = "✨ خوش اومدی ✨",
        parse_mode=None
):
    anon_mode = context.bot_data.get("anon_mode", False)
    markup = make_main_menu(anon_mode)
    chat_id = update.effective_chat.id
    menu_id = context.bot_data.get("menu_msg_id")

    # Try edit if it really changed
    if await message_exists(context, chat_id, ADMIN_ID, menu_id):
        if text != context.bot_data.get("menu_msg", ""):
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=menu_id,
                    text=text,
                    reply_markup=markup,
                    parse_mode=parse_mode
                )
                context.bot_data["menu_msg"] = text
                return
            except BadRequest as e:
                print(e)

    else:
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=markup,
            parse_mode=parse_mode
        )
        context.bot_data["menu_msg_id"] = sent.message_id
        context.bot_data["menu_msg"] = text


async def message_exists(context, from_chat, to_chat, message_id):
    try:
        fwd_msg = await context.bot.forward_message(chat_id=to_chat, from_chat_id=from_chat, message_id=message_id)
        await context.bot.delete_message(chat_id=to_chat, message_id=fwd_msg.message_id)
        return True
    except BadRequest as e:
        # Explicitly check for the specific error message
        if "Message to forward not found" in e.message:
            return False
        else:
            raise


# ─── COMMANDS ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await manage_main_menu(update, context)


async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"Your Telegram user ID is: {update.effective_user.id}")


# ─── CALLBACKS ────────────────────────────────────────────────────────────────
async def on_toggle_anon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    current = context.bot_data.get("anon_mode", False)
    context.bot_data["anon_mode"] = not current
    await query.edit_message_text(
        f"در حالت ناشناس هستید. پیام خود را بفرستید"
        if not current
        else "حالت ناشناس خاموش است.",
        reply_markup=make_main_menu(update.effective_user.id == ADMIN_ID, not current)
    )


async def on_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pattern = r"^anonreply_([A-Za-z0-9]+)_(\d+)$"
    admin_chat_msg_id = query.message.message_id

    anon_id, anon_chat_msg_id = re.match(pattern, query.data).groups()
    print(admin_chat_msg_id, anon_chat_msg_id)
    context.bot_data["reply_to"] = anon_id
    await query.edit_message_reply_markup(
        reply_markup=make_response_menu(anon_id)
    )


async def on_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    help_text = (
        " <b>❕قوانین</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "‼️ اگه تند تند و زیاد پیام بفرستی بن خواهی شد!\n"
        "\n\n"
        "📌 <b>دستورات ربات</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🟢 <code>/start</code> – نمایش منوی اصلی\n"
        "🆔 <code>/id</code>    – نمایش شناسه عددی شما\n\n"
        "✨ <b>قابلیت‌ها</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕶️ <b>حالت ناشناس:</b> چت کردن به صورت ناشناس با {ADMIN_NAME}\n"
        "🗑️ <b>پاکسازی پیام‌ها:</b> حذف راحت پیام های اخیر در چت به جز پیام منو\n"
        "📣 <i>برای پیشنهادات یا گزارش باگ، به ادمین پیام دهید.</i>"
    )
    await manage_main_menu(update, context, text=help_text, parse_mode=ParseMode.HTML)


async def on_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    await query.answer()
    menu_msg_id = context.bot_data.get("menu_msg_id", "")
    # delete all messages except the one with menu buttons
    x = context.bot_data.get("deleted_msgs", 1) * 10
    for msg_id in list(range(menu_msg_id - x, menu_msg_id)) + list(range(menu_msg_id + 1, menu_msg_id + x)):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except BadRequest as e:
            print(e)
    context.bot_data["deleted_msgs"] = +1


async def on_cancel_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


# ─── MESSAGE HANDLERS ─────────────────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message

    if user_id == ADMIN_ID and "reply_to" in context.bot_data:
        anon_id = context.bot_data.pop("reply_to")
        target_user = decode(anon_id)
        await context.bot.send_message(chat_id=target_user,
                                       text=f"💬 <b>{ADMIN_NAME}</b>\n {msg.text}",
                                       parse_mode="HTML"
                                       )
        await update.message.reply_text("✅.")
        return

    if user_id != ADMIN_ID and context.bot_data.get("anon_mode", False):
        anon_id = encode(user_id)
        print(msg.id)
        keyboard = InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(f"{anon_id}پاسخ به ", callback_data=f"anonreply_{anon_id}_{msg.id}")
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=msg.text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await update.message.reply_text("✅.")
        await manage_main_menu(update, context, text='اگر پیام دیگه ای داری اون رو هم بفرست')
        return

    await manage_main_menu(update, context, text='اگر میخوای پیامی بفرستی باید اول وارد حالت ناشناس بشی')


# ─── SETUP & POLLING ───────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CallbackQueryHandler(on_toggle_anon, pattern="^toggle_anon$"))
    app.add_handler(CallbackQueryHandler(on_help, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(on_cleanup, pattern="^cleanup$"))
    app.add_handler(CallbackQueryHandler(on_reply, pattern=r"^anonreply_[\dA-Za-z]+_\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()


if __name__ == "__main__":
    main()
