import logging
import os
import signal
import sys
from html import escape
from typing import Optional

from dotenv import load_dotenv
from telegram import Chat, Update, User
from telegram.constants import ChatMemberStatus
from telegram.error import BadRequest, Forbidden
from telegram.ext import Application, CommandHandler, ContextTypes


ADMIN_STATUSES = {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}

HELP_TEXT = (
    "🤖 <b>ID Vault Bot</b>\n\n"
    "<b>Commands:</b>\n"
    "/myid — show your user/admin ID\n"
    "/id — show the current group/channel ID (admins only)\n"
    "/id @username — show a public group/channel ID (target chat admins only)\n"
    "/admins — show admin IDs for the current group/channel (admins only)\n"
    "/admins @username — show admin IDs for a public group/channel (target chat admins only)\n"
    "/help — show this message again"
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def chat_type_label(chat: Chat) -> str:
    labels = {
        Chat.PRIVATE: "Private",
        Chat.GROUP: "Group",
        Chat.SUPERGROUP: "Supergroup",
        Chat.CHANNEL: "Channel",
    }
    return labels.get(chat.type, chat.type or "Unknown")


def format_chat(chat: Chat) -> str:
    username = f"@{chat.username}" if chat.username else "N/A"
    title = escape(chat.title or chat.full_name or "N/A")
    return (
        "📋 <b>Chat Details</b>\n"
        f"Name: <code>{title}</code>\n"
        f"Type: <code>{escape(chat_type_label(chat))}</code>\n"
        f"ID: <code>{chat.id}</code>\n"
        f"Username: <code>{escape(username)}</code>"
    )


def format_user(user: User) -> str:
    username = f"@{user.username}" if user.username else "N/A"
    return (
        "👤 <b>Your Details</b>\n"
        f"Name: <code>{escape(user.full_name)}</code>\n"
        f"User ID: <code>{user.id}</code>\n"
        f"Username: <code>{escape(username)}</code>"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def get_requester(update: Update) -> Optional[User]:
    """
    Returns the effective user who sent the command.
    In channel posts, Telegram does not provide a real user ID — the user is guided accordingly.
    """
    user = update.effective_user
    if user:
        return user

    if update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Telegram did not send a user ID with this command.\n\n"
            "Commands do not work inside channels. Open the bot in private chat and use:\n"
            "/id @public_channel_username\n"
            "/admins @public_channel_username"
        )
    return None


async def is_admin(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int | str, user_id: int
) -> bool:
    """Returns True if the user is an admin or owner of the given chat."""
    member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    return member.status in ADMIN_STATUSES


async def require_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | str,
    user_id: int,
) -> bool:
    """
    Returns True if the user is an admin, otherwise sends an error message and returns False.
    """
    try:
        if await is_admin(context, chat_id, user_id):
            return True
    except (BadRequest, Forbidden) as exc:
        logger.info("Admin check failed for chat %s: %s", chat_id, exc)
        if update.effective_message:
            await update.effective_message.reply_text(
                "⛔ Cannot access this chat or channel.\n\n"
                "Please check:\n"
                "1. The bot is added to the target group or channel.\n"
                "2. For channels, the bot may need to be an admin.\n"
                "3. For private groups or channels, use the command inside that chat instead of a username."
            )
        return False

    if update.effective_message:
        await update.effective_message.reply_text(
            "🚫 Access denied. You must be an admin of this group or channel to use this command."
        )
    return False


async def resolve_target_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target: Optional[str],
    command_hint: str,
) -> Optional[Chat]:
    """
    Resolves the target chat:
    - If a username is provided, fetches that chat.
    - Otherwise uses the current chat (not allowed in private chats).
    Returns a Chat object or None on failure.
    """
    message = update.effective_message

    if target:
        try:
            return await context.bot.get_chat(target)
        except (BadRequest, Forbidden):
            if message:
                await message.reply_text(
                    f"❌ Chat not found or the bot cannot access it.\n"
                    f"Use a public username: {command_hint} @channelname\n"
                    f"Or add the bot to the target chat first."
                )
            return None

    chat = update.effective_chat
    if chat and chat.type == Chat.PRIVATE:
        if message:
            await message.reply_text(
                f"ℹ️ Use this command inside a group or channel,\n"
                f"or in private chat with a username: {command_hint} @public_username"
            )
        return None

    return chat


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_html(HELP_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_html(HELP_TEXT)


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await get_requester(update)
    if not user:
        return
    if update.effective_message:
        await update.effective_message.reply_html(format_user(user))


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await get_requester(update)
    if not user:
        return

    target = context.args[0] if context.args else None
    chat = await resolve_target_chat(update, context, target, "/id")
    if not chat:
        return

    if not await require_admin(update, context, chat.id, user.id):
        return

    if update.effective_message:
        await update.effective_message.reply_html(format_chat(chat))


async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await get_requester(update)
    if not user:
        return

    target = context.args[0] if context.args else None
    chat = await resolve_target_chat(update, context, target, "/admins")
    if not chat:
        return

    if not await require_admin(update, context, chat.id, user.id):
        return

    try:
        admin_members = await context.bot.get_chat_administrators(chat.id)
    except (BadRequest, Forbidden):
        if update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ The bot needs admin permissions in this chat to fetch the admin list."
            )
        return

    lines = [format_chat(chat), "", "👥 <b>Admins</b>"]
    for member in admin_members:
        admin = member.user
        username = f"@{admin.username}" if admin.username else "N/A"
        lines.append(
            f"• <code>{admin.id}</code> | {escape(admin.full_name)} | <code>{escape(username)}</code>"
        )

    if update.effective_message:
        await update.effective_message.reply_html("\n".join(lines))


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Something went wrong. Please check the logs."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is missing. Set BOT_TOKEN in the .env file.")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("admins", admins_command))
    application.add_error_handler(error_handler)

    def _shutdown(sig, frame):  # noqa: ANN001
        logger.info("Shutdown signal received (%s), stopping bot...", sig)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
