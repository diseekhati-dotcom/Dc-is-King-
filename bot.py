import os
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from anime_service import find_anime, format_result


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("anime-hindi-info-bot")


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎌 Anime Hindi Info Bot\n\n"
        "Use:\n/anime <anime name>\n\n"
        "Example:\n/anime Black Torch"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/anime <name> — verified anime information\n"
        "/help — show this help"
    )


async def anime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args).strip()

    if not name:
        await update.message.reply_text(
            "❌ Anime name missing.\n\n"
            "Use:\n/anime <anime name>"
        )
        return

    msg = await update.message.reply_text(
        "🔎 Official sources check ho rahe hain..."
    )

    try:
        data = await find_anime(name)
        await msg.edit_text(format_result(data)[:4096])
    except Exception:
        log.exception("Anime lookup failed for %s", name)
        await msg.edit_text(
            "⚠️ Verified information fetch nahi ho saki.\n"
            "Thodi der baad dobara try karo."
        )


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("anime", anime_cmd))

    log.info("Bot initialized successfully")
    log.info("Starting Telegram polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
    
