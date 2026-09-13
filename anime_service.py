 import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

from openai import AsyncOpenAI


# IMPORTANT:
# This service does NOT use Rare Toon, DC, download sites,
# Telegram channels, or any unofficial scraper.
PLATFORMS = [
    "Crunchyroll",
    "Netflix",
    "JioHotstar",
    "Amazon Prime Video",
    "Amazon MX Player",
    "Sony YAY!",
    "SonyLIV",
    "YouTube",
    "Muse India",
    "Ani-One Asia",
    "Ani-One India",
    "Animax",
    "Cartoon Network",
    "Nickelodeon",
    "ZEE5",
    "Anime Times",
]


@dataclass
class AnimeData:
    title: str
    hindi: bool = False
    platform: str = "Not verified"

    season: str = "Not verified"
    episodes: Optional[int] = None

    # Hindi progress is kept SEPARATE from total episode progress.
    hindi_episodes: Optional[int] = None
    last_hindi_episode: Optional[int] = None
    next_hindi_episode: Optional[int] = None
    hindi_expected_release: Optional[str] = None

    languages: List[str] = field(default_factory=list)
    status: str = "Not verified"

    last_episode: Optional[int] = None
    last_release: Optional[str] = None
    next_episode: Optional[int] = None
    expected_release: Optional[str] = None
    schedule: Optional[str] = None

    studio: str = "Not verified"
    dub_by: str = "Not verified"

    source: str = "Not verified"
    platform_checks: List[dict] = field(default_factory=list)


def get_openai_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")
    return AsyncOpenAI(api_key=api_key)


def to_int(value) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_json(raw: str) -> str:
    raw = raw.strip()

    if raw.startswith("```"):
        if raw.startswith("```json"):
            raw = raw[7:]
        else:
            raw = raw[3:]

        if raw.endswith("```"):
            raw = raw[:-3]

    return raw.strip()


async def find_anime(name: str) -> AnimeData:
    anime_name = name.strip()

    if not anime_name:
        raise ValueError("Anime name missing.")

    client = get_openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

    platforms = "\n".join(f"- {p}" for p in PLATFORMS)

    prompt = f"""
You are a CURRENT WEB anime verification agent for an Indian Telegram bot.

USER SEARCH:
{anime_name}

Your task is to search the current web and return verified anime information.

HARD RULES:
1. Do NOT answer from memory alone.
2. Do NOT use Rare Toon.
3. Do NOT use DC.
4. Do NOT use anime download/piracy sites.
5. Do NOT use Telegram download channels.
6. Do NOT use unofficial scraped download pages.
7. Prefer official anime, publisher, studio and streaming-platform sources.
8. For Indian availability, prefer India-specific official information.
9. Hindi audio/dub is NOT the same as Hindi subtitles.
10. Never mark the whole anime as Hindi dubbed just because Hindi is listed
    somewhere for the title.
11. Total episodes and Hindi-dubbed episodes MUST remain separate.
12. Never copy "episodes" into "hindi_episodes".
13. For an ongoing anime, verify total latest episode and Hindi latest episode
    independently.
14. Never invent an episode number, date, platform, language or schedule.
15. If a field cannot be verified, use null or "Not verified".
16. source_url values must be real URLs actually found during the search.
17. Do not fabricate example URLs.

PLATFORMS TO CHECK:
{platforms}

SOURCE PRIORITY:
1. Official anime / publisher / studio website
2. Official streaming-platform page
3. Official episode/audio-language page
4. Official YouTube channel
5. Official announcement/social account
6. Reliable anime database/news as secondary confirmation

HINDI DUB VERIFICATION:
Hindi is verified only when reliable evidence confirms Hindi AUDIO.
Hindi subtitles do not count.

EPISODE VERIFICATION:
- episodes = total currently released/listed episodes
- last_episode = latest currently released episode
- last_release = latest episode release date if verified
- next_episode = next announced/upcoming episode if verified
- expected_release = official expected date if verified
- schedule = verified release schedule if available

HINDI EPISODE VERIFICATION:
- hindi_episodes = number of episodes with verified Hindi audio
- last_hindi_episode = latest episode with verified Hindi audio
- next_hindi_episode = next episode expected in Hindi, only if verified
- hindi_expected_release = official expected Hindi release date, only if verified

IMPORTANT:
If total episodes are 10 and only 3 are verified in Hindi:
episodes MUST be 10
hindi_episodes MUST be 3
last_hindi_episode MUST be 3
Do NOT make hindi_episodes equal to 10.

STATUS:
Use "🟢 Ongoing", "🔵 Completed", "⏸ Hiatus", or "Not verified".

Return ONLY valid JSON with this exact structure.
Unknown values must be null or "Not verified".

{{
  "title": "",
  "hindi": false,
  "platform": "Not verified",
  "season": "Not verified",
  "episodes": null,
  "hindi_episodes": null,
  "last_hindi_episode": null,
  "next_hindi_episode": null,
  "hindi_expected_release": null,
  "languages": [],
  "status": "Not verified",
  "last_episode": null,
  "last_release": null,
  "next_episode": null,
  "expected_release": null,
  "schedule": "Not verified",
  "studio": "Not verified",
  "dub_by": "Not verified",
  "source": "Not verified",
  "platform_checks": [
    {{
      "platform": "",
      "found": false,
      "hindi": false,
      "languages": [],
      "episodes": null,
      "verified": false,
      "source_url": null
    }}
  ]
}}
"""

    try:
        response = await client.responses.create(
            model=model,
            tools=[{"type": "web_search"}],
            input=prompt,
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI web verification failed: {exc}") from exc

    raw = clean_json(response.output_text)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "OpenAI returned invalid JSON. Please try the anime search again."
        ) from exc

    checks = []
    for item in result.get("platform_checks") or []:
        if not isinstance(item, dict):
            continue

        checks.append(
            {
                "platform": str(item.get("platform") or "Not verified"),
                "found": bool(item.get("found", False)),
                "hindi": bool(item.get("hindi", False)),
                "languages": [
                    str(x) for x in (item.get("languages") or [])
                ],
                "episodes": to_int(item.get("episodes")),
                "verified": bool(item.get("verified", False)),
                "source_url": item.get("source_url"),
            }
        )

    title = str(result.get("title") or anime_name).strip()

    return AnimeData(
        title=title,
        hindi=bool(result.get("hindi", False)),
        platform=str(result.get("platform") or "Not verified"),
        season=str(result.get("season") or "Not verified"),
        episodes=to_int(result.get("episodes")),
        hindi_episodes=to_int(result.get("hindi_episodes")),
        last_hindi_episode=to_int(result.get("last_hindi_episode")),
        next_hindi_episode=to_int(result.get("next_hindi_episode")),
        hindi_expected_release=result.get("hindi_expected_release"),
        languages=[
            str(x) for x in (result.get("languages") or [])
        ],
        status=str(result.get("status") or "Not verified"),
        last_episode=to_int(result.get("last_episode")),
        last_release=result.get("last_release"),
        next_episode=to_int(result.get("next_episode")),
        expected_release=result.get("expected_release"),
        schedule=result.get("schedule"),
        studio=str(result.get("studio") or "Not verified"),
        dub_by=str(result.get("dub_by") or "Not verified"),
        source=str(result.get("source") or "Not verified"),
        platform_checks=checks,
    )


def show(value) -> str:
    if value is None or value == "" or value == []:
        return "Not verified"
    return str(value)


def episode(value) -> str:
    return f"Episode {value}" if value is not None else "Not verified"


def format_result(d: AnimeData) -> str:
    languages = ", ".join(d.languages) if d.languages else "Not verified"
    dub = "Hindi" if d.hindi else "Not verified"

    return (
        f"🎌 Anime: {d.title}\n\n"
        f"🇮🇳 Dub: {dub}\n"
        f"📺 Platform: {show(d.platform)}\n\n"
        f"📚 Season: {show(d.season)}\n"
        f"🎬 Episodes: {show(d.episodes)}\n\n"
        f"🌐 Languages: {languages}\n"
        f"📌 Status: {show(d.status)}\n\n"
        f"🎬 Last Episode: {episode(d.last_episode)}\n"
        f"⏭️ Next Episode: {episode(d.next_episode)}\n"
        f"📅 Expected: {show(d.expected_release)}\n\n"
        f"🇮🇳 Hindi Episodes: {show(d.hindi_episodes)}\n"
        f"🇮🇳 Last Hindi Episode: {episode(d.last_hindi_episode)}\n"
        f"⏭️ Next Hindi Episode: {episode(d.next_hindi_episode)}\n"
        f"📅 Hindi Expected: {show(d.hindi_expected_release)}"
    )
    
