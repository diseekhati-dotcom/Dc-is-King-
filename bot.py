"""
bot.py
Telegram entry point for the official-source anime information bot.

Required Render variables:
    TELEGRAM_BOT_TOKEN
    SERPAPI_KEY

BOT_TOKEN is also accepted for compatibility with older Render setups.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from anime_service import BUILD_ID, AnimeResult, format_result, get_anime_info


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("anime_info_bot")

# Accept the Render variable used by render.yaml, plus the old name so
# an existing deployment does not break during migration.
BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    or os.getenv("BOT_TOKEN", "").strip()
)

HELP_TEXT = """ðŸŽŒ Anime Info Bot

Use:
/anime <anime name>

Examples:
/anime One Piece
/anime Naruto
/anime Black Torch

The bot checks approved official/authorized sources only.
Unofficial anime download/streaming sites are not used.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT)


async def help_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT)


async def version_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.message:
        await update.message.reply_text(
            f"âœ… Anime Info Bot\n"
            f"Build: {BUILD_ID}\n"
            f"Service: anime_service.py\n"
            f"Source policy: official/authorized only"
        )


async def anime_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message:
        return

    title = " ".join(context.args).strip()

    if not title:
        await update.message.reply_text(
            "âŒ Anime name missing.\n\n"
            "Example:\n"
            "/anime One Piece"
        )
        return

    searching = await update.message.reply_text(
        f"ðŸ”Ž Official sources check kar raha hoon...\n\nðŸŽŒ {title}"
    )

    try:
        data = await get_anime_info(title)
        result = AnimeResult(**data)
        text = format_result(result)

        # Keep output safely below Telegram's message limit.
        if len(text) > 3800:
            text = text[:3750] + "\n\nâ€¦Output shortened."

        await searching.edit_text(text)

    except Exception:
        logger.exception("Anime lookup failed for %r", title)
        await searching.edit_text(
            "âŒ Anime information fetch nahi ho saki.\n\n"
            "Official search service temporarily unavailable ho sakta hai.\n"
            "Thodi der baad dobara try karo."
        )


async def error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    logger.exception("Telegram error: %s", context.error)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "Telegram token missing. Set TELEGRAM_BOT_TOKEN in Render "
            "Environment Variables."
        )

    logger.info("BOT_BUILD=%s", BUILD_ID)
    logger.info("anime_service=%s", Path(__file__).with_name("anime_service.py"))

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("version", version_command))
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
