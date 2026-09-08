"""
Anime verification service.

Flow:
Telegram -> this service -> OpenAI Responses API -> Web Search
-> source verification -> structured anime result

IMPORTANT:
- The model must use web sources for current information.
- It must NOT invent Hindi dubbing, platform, episode or release data.
- If something cannot be verified, it returns "Not verified".
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

from openai import AsyncOpenAI


PLATFORMS = [
    "Sony YAY!",
    "SonyLIV",
    "Crunchyroll",
    "Netflix",
    "JioHotstar",
    "Amazon MX Player",
    "Prime Video / Anime Times",
    "ZEE5",
    "Muse India",
    "Ani-One India",
    "Anime Times",
]


@dataclass
class PlatformVerification:
    platform: str
    found: bool = False
    hindi: bool = False
    languages: List[str] = field(default_factory=list)
    episodes: Optional[int] = None
    verified: bool = False
    source_url: Optional[str] = None


@dataclass
class AnimeData:
    title: str
    hindi: bool = False
    platform: str = "Not verified"
    season: str = "Not verified"
    episodes: Optional[int] = None
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
    platform_checks: List[PlatformVerification] = field(default_factory=list)


def _client():
    key = os.getenv("OPENAI_API_KEY")

    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is missing."
        )

    return AsyncOpenAI(api_key=key)


async def find_anime(name: str) -> AnimeData:

    query = name.strip()

    if not query:
        raise ValueError("Please enter an anime name.")

    client = _client()

    platforms_text = ", ".join(PLATFORMS)

    prompt = f"""
You are an anime information verification agent.

Search the web before answering.

User searched for:
{query}

TARGET PLATFORMS:
{platforms_text}

TASK:

Find the correct anime and verify its information using
reliable current web sources.

PRIORITY OF SOURCES:

1. Official platform pages
2. Official anime/studio/publisher pages
3. Official YouTube channels
4. Reliable anime databases for neutral metadata
5. Other reputable sources only when necessary

For Hindi dubbing:
- Do NOT assume Hindi exists.
- Do NOT infer Hindi from subtitles.
- Only mark Hindi as available when a source supports it.

For platform:
- Only name a platform when the anime is actually available
  or officially announced there.
- Prefer Indian-region availability when possible.

For episodes:
- Cross-check episode count.
- For currently airing anime, find the latest released episode.
- Find the next episode only when a reliable current source
  provides enough information.
- NEVER guess a release date.

Check the following platforms individually when relevant:
{platforms_text}

Return ONLY valid JSON.

Required JSON format:

{{
  "title": "Anime title",
  "hindi": false,
  "platform": "Not verified",
  "season": "Season 1",
  "episodes": 12,
  "languages": ["Japanese", "English", "Hindi"],
  "status": "🟢 Ongoing",
  "last_episode": 10,
  "last_release": "2026-09-05",
  "next_episode": 11,
  "expected_release": "2026-09-12",
  "schedule": "Every Saturday",
  "studio": "Studio name",
  "dub_by": "Not verified",
  "source": "Official sources",
  "platform_checks": [
    {{
      "platform": "Crunchyroll",
      "found": true,
      "hindi": true,
      "languages": ["Japanese", "English", "Hindi"],
      "episodes": 12,
      "verified": true,
      "source_url": "https://..."
    }}
  ]
}}

RULES:

- Use "Not verified" instead of guessing.
- Boolean fields must be true/false.
- episodes, last_episode and next_episode must be numbers
  or null.
- If Hindi cannot be verified, hindi=false.
- If no platform can be verified, platform="Not verified".
- Do not manufacture URLs.
- Use source URLs actually found during web search.
"""

    response = await client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        tools=[
            {
                "type": "web_search"
            }
        ],
        input=prompt,
    )

    text = response.output_text.strip()

    # Remove accidental markdown fences.
    if text.startswith("```"):
        text = text.replace("```json", "", 1)
        text = text.replace("```", "")
        text = text.strip()

    try:
        data = json.loads(text)

    except json.JSONDecodeError:
        raise ValueError(
            "The verification service returned an invalid result. "
            "Please try again."
        )

    platform_checks = []

    for item in data.get("platform_checks", []):

        if not isinstance(item, dict):
            continue

        platform_checks.append(
            PlatformVerification(
                platform=str(
                    item.get("platform", "Not verified")
                ),
                found=bool(item.get("found", False)),
                hindi=bool(item.get("hindi", False)),
                languages=item.get("languages") or [],
                episodes=item.get("episodes"),
                verified=bool(item.get("verified", False)),
                source_url=item.get("source_url"),
            )
        )

    return AnimeData(
        title=str(
            data.get("title") or query
        ).upper(),

        hindi=bool(
            data.get("hindi", False)
        ),

        platform=str(
            data.get("platform") or "Not verified"
        ),

        season=str(
            data.get("season") or "Not verified"
        ),

        episodes=data.get("episodes"),

        languages=data.get("languages") or [],

        status=str(
            data.get("status") or "Not verified"
        ),

        last_episode=data.get("last_episode"),

        last_release=data.get("last_release"),

        next_episode=data.get("next_episode"),

        expected_release=data.get(
            "expected_release"
        ),

        schedule=data.get("schedule"),

        studio=str(
            data.get("studio") or "Not verified"
        ),

        dub_by=str(
            data.get("dub_by") or "Not verified"
        ),

        source=str(
            data.get("source") or "Web verified"
        ),

        platform_checks=platform_checks,
    )


def format_result(d: AnimeData) -> str:

    eps = (
        str(d.episodes)
        if d.episodes is not None
        else "Not verified"
    )

    langs = (
        " • ".join(d.languages)
        if d.languages
        else "Not verified"
    )

    last_ep = (
        f"Episode {d.last_episode}"
        if d.last_episode is not None
        else "Not verified"
    )

    next_ep = (
        f"Episode {d.next_episode}"
        if d.next_episode is not None
        else "Not verified"
    )

    hindi = (
        "✅ Available"
        if d.hindi
        else "❌ Not verified"
    )

    return f"""🎬 Anime: {d.title}

🇮🇳 Hindi Dub: {hindi}
📺 Platform: {d.platform}
📀 Season: {d.season}
🎬 Episodes: {eps}

🌐 Languages: {langs}

📊 Status: {d.status}

📅 Last Episode: {last_ep}
🗓 Last Release: {d.last_release or "Not verified"}

⏭ Next Episode: {next_ep}
📅 Expected Release: {d.expected_release or "Not verified"}
⏰ Schedule: {d.schedule or "Not verified"}

🏢 Studio: {d.studio}
🎙 Dub By: {d.dub_by}

🔎 Source: {d.source}
"""
