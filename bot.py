"""
bot.py
Telegram bot for anime_service.py

Install:
    pip install python-telegram-bot httpx beautifulsoup4

Environment:
    BOT_TOKEN=your_telegram_bot_token
    SERPAPI_KEY=your_serpapi_key

Run:
    python bot.py
"""

import os
import logging
from html import escape

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from anime_service import get_anime_info, AnimeResult, format_result


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("anime_info_bot")


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()


HELP_TEXT = """🎌 Anime Info Bot

Use:
 /anime <anime name>

Examples:
 /anime One Piece
 /anime Naruto
 /anime Black Torch

The bot checks official/authorized platform results and does not use
unofficial anime download or streaming websites.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def anime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    title = " ".join(context.args).strip()

    if not title:
        await update.message.reply_text(
            "❌ Anime name missing.\n\n"
            "Example:\n"
            "/anime One Piece"
        )
        return

    # Telegram message length is limited. This keeps the user-facing
    # response safely below the limit.
    searching = await update.message.reply_text(
        f"🔎 Official sources check kar raha hoon...\n\n🎌 {title}"
    )

    try:
        data = await get_anime_info(title)
        result = AnimeResult(**data)

        text = format_result(result)

        # Escape only when sending as plain text. URLs are intentionally
        # left as plain text because Telegram clients can make them clickable.
        await searching.edit_text(text)

    except Exception as exc:
        logger.exception("Anime lookup failed: %s", exc)
        await searching.edit_text(
            "❌ Anime information fetch nahi ho saki.\n\n"
            "Official source temporarily unavailable ho sakta hai.\n"
            "Thodi der baad dobara try karo."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Telegram error: %s", context.error)


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable missing. "
            "Render Environment Variables me BOT_TOKEN set karo."
        )

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("anime", anime_command))

    application.add_error_handler(error_handler)

    logger.info("Bot initialized successfully")
    logger.info("Starting Telegram polling...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
    
