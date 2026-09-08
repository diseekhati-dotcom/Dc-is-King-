# Anime Telegram Bot

A Telegram bot skeleton for verified anime metadata and Hindi-dub checking.

## Security

Never put Telegram or OpenAI keys in the source code or send them in chat.
Set them as cloud environment variables:

- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Android/Termux: source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## Current behavior

`/anime <name>` returns the requested fixed layout. The project deliberately
returns "Not verified" until a source adapter has actually verified a claim.

## Next module

Add official/public source adapters for:
Sony YAY!, SonyLIV, Crunchyroll, Netflix, JioHotstar,
Amazon MX Player, Prime Video/Anime Times, ZEE5, Muse India, Ani-One India.

Do not mark Hindi as available merely because an anime exists on a platform.
Each language/platform claim should carry a source URL and verification time.
