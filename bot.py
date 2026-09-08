import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from openai import AsyncOpenAI

from anime_service import find_anime, format_result

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("anime-bot")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You format verified anime metadata for a Telegram bot.
Never invent a platform, Hindi dub, episode count, release date, schedule,
studio, dub provider, or language. The supplied metadata is the source of truth.
If a field is unknown, write "Not verified".
Keep the exact output structure supplied by the application.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Anime Bot\n\n"
        "Use /anime <anime name>\n"
        "Example: /anime BLACK TORCH"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/anime <name> — anime information\n"
        "/latest — latest verified updates (coming soon)"
    )

async def anime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args).strip()
    if not name:
        await update.message.reply_text("Use: /anime <anime name>")
        return

    msg = await update.message.reply_text("🔎 Checking verified sources…")

    try:
        data = await find_anime(name)
        raw = format_result(data)

        # AI is used only as a formatter, not as the verification source.
        response = await ai.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            instructions=SYSTEM_PROMPT,
            input=raw,
        )
        answer = response.output_text.strip()
        await msg.edit_text(answer[:4096])
    except Exception as exc:
        log.exception("Anime lookup failed")
        await msg.edit_text(
            "⚠️ Verification failed right now.\n"
            "Please try again later."
        )

async def latest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⏳ Automatic latest-update checker is the next module."
    )

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("anime", anime_cmd))
    app.add_handler(CommandHandler("latest", latest_cmd))
    log.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
