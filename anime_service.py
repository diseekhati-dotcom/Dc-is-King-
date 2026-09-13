"""
Anime Verification Service

Flow:
Telegram user
    ↓
Anime name
    ↓
OpenAI Responses API
    ↓
Web Search
    ↓
Official/public sources
    ↓
Cross-check
    ↓
Verified JSON
    ↓
Telegram bot

IMPORTANT:
- OPENAI_API_KEY must be stored in Render Environment Variables.
- Never put the API key directly inside this file.
- Never guess Hindi dubbing or platform availability.
- If information cannot be verified, return "Not verified".
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

from openai import AsyncOpenAI


# ============================================================
# PLATFORMS TO CHECK
# ============================================================

PLATFORMS = [
    "Sony YAY!",
    "SonyLIV",
    "Crunchyroll",
    "Netflix",
    "JioHotstar",
    "Amazon MX Player",
    "Prime Video",
    "Anime Times",
    "ZEE5",
    "Muse India",
    "Ani-One India",
]


# ============================================================
# DATA STRUCTURES
# ============================================================

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

    platform_checks: List[PlatformVerification] = field(
        default_factory=list
    )


# ============================================================
# OPENAI CLIENT
# ============================================================

def get_openai_client():

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. "
            "Add it in Render → Environment."
        )

    return AsyncOpenAI(api_key=api_key)


# ============================================================
# SEARCH / VERIFICATION
# ============================================================

async def find_anime(name: str) -> AnimeData:

    anime_name = name.strip()

    if not anime_name:
        raise ValueError(
            "Please enter an anime name."
        )

    client = get_openai_client()

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-5-mini"
    )

    platforms = "\n".join(
        f"- {platform}"
        for platform in PLATFORMS
    )

    prompt = f"""
You are an expert anime verification agent.

The Telegram user searched for:

{anime_name}

Your job is to SEARCH THE CURRENT WEB and verify the anime.

DO NOT answer from memory alone.

============================================================
PLATFORMS TO CHECK
============================================================

{platforms}

============================================================
SOURCE PRIORITY
============================================================

Use sources in this priority:

1. Official anime / publisher / studio websites
2. Official streaming platform pages
3. Official YouTube channels
4. Official social media announcements
5. Reliable anime databases
6. Reliable news sources

For Indian availability, prioritize Indian-region information.

============================================================
HINDI DUB VERIFICATION
============================================================

Hindi dubbing must NOT be guessed.

Hindi is VERIFIED only when a reliable source confirms it. Hindi subtitles do NOT count as Hindi dubbing. Never assume every episode is dubbed just because Hindi is listed for the series.

Examples of evidence:

- Hindi audio listed on an official streaming page
- Official Hindi dub announcement
- Official Indian YouTube announcement
- Official platform audio-language information

Hindi subtitles do NOT mean Hindi dub.

If Hindi dubbing cannot be confirmed:

"hindi": false

and do not claim that Hindi is available.

============================================================
PLATFORM VERIFICATION
============================================================

Check whether the anime is available or officially announced
on the listed platforms.

Do not assume that an anime exists on a platform merely because
the platform has anime content.

For every platform that can be verified, include it in
platform_checks.

If no reliable evidence exists:

verified = false

============================================================
EPISODE INFORMATION
============================================================

Find:

- total episodes currently released
- current/latest episode
- last release date
- next episode
- expected release date
- release schedule
- Hindi-dub episode count (SEPARATE from total episodes)
- latest episode with Hindi audio
- next Hindi-dub episode and official expected date, if available

Cross-check episode information.

Do NOT invent release dates.

If next episode/date cannot be confirmed:

return null / "Not verified".

============================================================
SEASON INFORMATION
============================================================

Use official or reliable information.

Examples:

Season 1
Season 2
Season 3

If the user searched for a franchise with multiple seasons,
identify the correct anime entry.

============================================================
LANGUAGES
============================================================

Only list languages that are actually supported by evidence.

Do not assume languages.

============================================================
DUB INFORMATION
============================================================

Find the Hindi dub studio / dubbing company / voice production
information only if reliable evidence exists.

Otherwise:

"Not verified"

============================================================
STUDIO
============================================================

Find the animation studio from a reliable source.

============================================================
CURRENT STATUS
============================================================

Possible examples:

🟢 Ongoing
🔵 Completed
⏸ Hiatus
Not verified

============================================================
VERY IMPORTANT
============================================================

NEVER hallucinate.

If something cannot be verified from web sources:

"Not verified"

The answer must be based on CURRENT web search results.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
    "title": "Anime title",

    "hindi": false,

    "platform": "Not verified",

    "season": "Season 1",

    "episodes": 12,
    "hindi_episodes": 3,
    "last_hindi_episode": 3,
    "next_hindi_episode": 4,
    "hindi_expected_release": "2026-09-20",

    "languages": [
        "Japanese",
        "English"
    ],

    "status": "🔵 Completed",

    "last_episode": 12,

    "last_release": "2026-09-05",

    "next_episode": null,

    "expected_release": null,

    "schedule": "Not verified",

    "studio": "Studio name",

    "dub_by": "Not verified",

    "source": "Official sources",

    "platform_checks": [
        {{
            "platform": "Crunchyroll",
            "found": true,
            "hindi": true,
            "languages": [
                "Japanese",
                "English",
                "Hindi"
            ],
            "episodes": 12,
            "verified": true,
            "source_url": "https://example.com"
        }}
    ]
}}

Rules:

- JSON only.
- No markdown.
- No explanation outside JSON.
- Boolean values must be true/false.
- Unknown information must be null or "Not verified".
- Never fabricate URLs.
- source_url must be a URL actually found during search.
"""

    try:

        response = await client.responses.create(

            model=model,

            tools=[
                {
                    "type": "web_search"
                }
            ],

            input=prompt
        )

    except Exception as e:

        raise RuntimeError(
            f"OpenAI request failed: {str(e)}"
        )


    raw = response.output_text.strip()


    # Remove accidental markdown fences
    if raw.startswith("```"):

        raw = raw.replace(
            "```json",
            "",
            1
        )

        raw = raw.replace(
            "```",
            ""
        )

        raw = raw.strip()


    try:

        result = json.loads(raw)

    except json.JSONDecodeError:

        raise RuntimeError(
            "OpenAI returned invalid JSON. "
            "Please try the search again."
        )


    # ========================================================
    # PLATFORM RESULTS
    # ========================================================

    platform_checks = []

    for item in result.get(
        "platform_checks",
        []
    ):

        if not isinstance(item, dict):
            continue

        platform_checks.append(

            PlatformVerification(

                platform=str(
                    item.get(
                        "platform",
                        "Not verified"
                    )
                ),

                found=bool(
                    item.get(
                        "found",
                        False
                    )
                ),

                hindi=bool(
                    item.get(
                        "hindi",
                        False
                    )
                ),

                languages=(
                    item.get(
                        "languages",
                        []
                    )
                    or []
                ),

                episodes=item.get(
                    "episodes"
                ),

                verified=bool(
                    item.get(
                        "verified",
                        False
                    )
                ),

                source_url=item.get(
                    "source_url"
                )
            )
        )


    # ========================================================
    # FINAL OBJECT
    # ========================================================

    return AnimeData(

        title=str(
            result.get(
                "title",
                anime_name
            )
        ).upper(),

        hindi=bool(
            result.get(
                "hindi",
                False
            )
        ),

        platform=str(
            result.get(
                "platform",
                "Not verified"
            )
            or "Not verified"
        ),

        season=str(
            result.get(
                "season",
                "Not verified"
            )
            or "Not verified"
        ),

        episodes=result.get(
            "episodes"
        ),

        hindi_episodes=result.get("hindi_episodes"),
        last_hindi_episode=result.get("last_hindi_episode"),
        next_hindi_episode=result.get("next_hindi_episode"),
        hindi_expected_release=result.get("hindi_expected_release"),

        languages=(
            result.get(
                "languages",
                []
            )
            or []
        ),

        status=str(
            result.get(
                "status",
                "Not verified"
            )
            or "Not verified"
        ),

        last_episode=result.get(
            "last_episode"
        ),

        last_release=result.get(
            "last_release"
        ),

        next_episode=result.get(
            "next_episode"
        ),

        expected_release=result.get(
            "expected_release"
        ),

        schedule=result.get(
            "schedule"
        ),

        studio=str(
            result.get(
                "studio",
                "Not verified"
            )
            or "Not verified"
        ),

        dub_by=str(
            result.get(
                "dub_by",
                "Not verified"
            )
            or "Not verified"
        ),

        source=str(
            result.get(
                "source",
                "Web verified"
            )
            or "Web verified"
        ),

        platform_checks=platform_checks
    )



# ============================================================
# TELEGRAM MESSAGE FORMAT
# ============================================================

def format_result(d: AnimeData) -> str:
    episodes = str(d.episodes) if d.episodes is not None else "Not verified"
    languages = ", ".join(d.languages) if d.languages else "Not verified"
    dub = "Hindi" if d.hindi else "Not verified"
    hindi_count = str(d.hindi_episodes) if d.hindi_episodes is not None else "Not verified"

    last_episode = f"Episode {d.last_episode}" if d.last_episode is not None else "Not verified"
    next_episode = f"Episode {d.next_episode}" if d.next_episode is not None else "Not verified"
    last_hindi = f"Episode {d.last_hindi_episode}" if d.last_hindi_episode is not None else "Not verified"
    next_hindi = f"Episode {d.next_hindi_episode}" if d.next_hindi_episode is not None else "Not verified"

    return (
        f"🎌 Anime: {d.title}\n\n"
        f"🇮🇳 Dub: {dub}\n"
        f"📺 Platform: {d.platform}\n\n"
        f"📚 Season: {d.season}\n"
        f"🎬 Episodes: {episodes}\n\n"
        f"🌐 Languages: {languages}\n"
        f"📌 Status: {d.status}\n\n"
        f"🎬 Last Episode: {last_episode}\n"
        f"⏭️ Next Episode: {next_episode}\n"
        f"📅 Expected: {d.expected_release or 'Not verified'}\n\n"
        f"🇮🇳 Hindi Episodes: {hindi_count}\n"
        f"🇮🇳 Last Hindi Episode: {last_hindi}\n"
        f"⏭️ Next Hindi Episode: {next_hindi}\n"
        f"📅 Hindi Expected: {d.hindi_expected_release or 'Not verified'}\n"
)
        
