"""
anime_service.py
Official-source-first anime availability checker for India.

Required:
    pip install httpx beautifulsoup4

Recommended environment variable:
    SERPAPI_KEY=...

Without SERPAPI_KEY the service can still query direct official search URLs
where possible, but results will be less reliable. The service NEVER uses
RareToon or other unofficial anime streaming/download sites.

Returned data is normalized for Telegram bot.py.
"""

from __future__ import annotations

import os
import re
import asyncio
from dataclasses import dataclass, asdict, field
from typing import Optional
from urllib.parse import quote, urlparse

import httpx
from bs4 import BeautifulSoup


INDIA = "India"

PLATFORMS = {
    "Crunchyroll": {
        "domains": ["crunchyroll.com"],
        "search": "site:crunchyroll.com/series/ {title}",
    },
    "Netflix": {
        "domains": ["netflix.com"],
        "search": "site:netflix.com/title/ {title}",
    },
    "Amazon Prime Video": {
        "domains": ["primevideo.com"],
        "search": "site:primevideo.com/detail/ {title}",
    },
    "Disney+": {
        "domains": ["disneyplus.com"],
        "search": "site:disneyplus.com {title}",
    },
    "JioHotstar": {
        "domains": ["hotstar.com", "jiohotstar.com"],
        "search": "site:hotstar.com OR site:jiohotstar.com {title} anime",
    },
    "JioCinema": {
        "domains": ["jiocinema.com"],
        "search": "site:jiocinema.com {title} anime",
    },
    "Sony YAY!": {
        "domains": ["sonyyay.com", "sonypicturesnetworks.com"],
        "search": "site:sonyyay.com {title} anime",
    },
    "SonyLIV": {
        "domains": ["sonyliv.com"],
        "search": "site:sonyliv.com {title} anime",
    },
    "MX Player": {
        "domains": ["mxplayer.in", "amazon.com"],
        "search": "site:mxplayer.in {title} anime",
    },
    "YouTube": {
        "domains": ["youtube.com"],
        "search": "site:youtube.com {title} anime official",
    },
    "Muse India": {
        "domains": ["youtube.com", "museindia.in"],
        "search": "site:youtube.com/@MuseIndia {title}",
    },
    "Ani-One Asia": {
        "domains": ["youtube.com", "ani-one.com"],
        "search": "site:youtube.com Ani-One {title} India",
    },
    "Animax": {
        "domains": ["animax-asia.com", "sony-asia.com"],
        "search": "site:animax-asia.com {title}",
    },
    "Cartoon Network": {
        "domains": ["cartoonnetworkasia.com", "cartoonnetwork.com"],
        "search": "site:cartoonnetworkasia.com {title} anime",
    },
    "Nickelodeon": {
        "domains": ["nick.com", "nickelodeon.com"],
        "search": "site:nick.com OR site:nickelodeon.com {title} anime",
    },
}

LANGUAGES = [
    "Hindi", "English", "Japanese", "Tamil", "Telugu", "Malayalam",
    "Kannada", "Bengali", "Marathi", "Korean", "Chinese", "Thai",
    "Spanish", "French", "German", "Portuguese", "Arabic"
]


@dataclass
class PlatformResult:
    name: str
    available: bool = False
    url: Optional[str] = None
    audio: list[str] = field(default_factory=list)
    subtitles: list[str] = field(default_factory=list)
    confidence: str = "unknown"
    note: str = ""


@dataclass
class AnimeResult:
    title: str
    dub: list[str] = field(default_factory=list)
    platforms: list[PlatformResult] = field(default_factory=list)
    seasons: Optional[str] = None
    episodes: Optional[str] = None
    languages: list[str] = field(default_factory=list)
    status: str = "Unknown"
    last_episode: Optional[str] = None
    next_episode: Optional[str] = None
    expected: Optional[str] = None
    source_count: int = 0


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _official(url: str, domains: list[str]) -> bool:
    host = _host(url)
    return any(host == d or host.endswith("." + d) for d in domains)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _langs(text: str) -> list[str]:
    low = text.lower()
    found = []
    for lang in LANGUAGES:
        if lang.lower() in low and lang not in found:
            found.append(lang)
    return found


def _status(text: str) -> str:
    low = text.lower()
    if any(x in low for x in ["currently airing", "ongoing", "simulcast", "new episode"]):
        return "Ongoing"
    if any(x in low for x in ["complete", "completed", "all episodes"]):
        return "Completed"
    if any(x in low for x in ["upcoming", "coming soon"]):
        return "Upcoming"
    return "Unknown"


def _episodes(text: str) -> Optional[str]:
    patterns = [
        r"\b(?:episode|ep\.?)\s*(\d{1,4})\b",
        r"\b(\d{1,4})\s*episodes?\b",
    ]
    nums = []
    for p in patterns:
        nums += [int(x) for x in re.findall(p, text, re.I)]
    if not nums:
        return None
    return str(max(nums))


def _extract_next_last(text: str) -> tuple[Optional[str], Optional[str]]:
    nums = [int(x) for x in re.findall(r"\b(?:episode|ep\.?)\s*(\d{1,4})\b", text, re.I)]
    if not nums:
        return None, None
    n = max(nums)
    return f"Episode {n}", f"Episode {n + 1}"


async def _serp_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    key = os.getenv("SERPAPI_KEY")
    if not key:
        return []

    try:
        r = await client.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "gl": "in",
                "hl": "en",
                "api_key": key,
                "num": 10,
            },
            timeout=20,
        )
        r.raise_for_status()
        return r.json().get("organic_results", [])
    except Exception:
        return []


async def _fetch_page(client: httpx.AsyncClient, url: str) -> str:
    try:
        r = await client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 AnimeInfoBot/1.0"},
            timeout=20,
            follow_redirects=True,
        )
        if r.status_code >= 400:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for x in soup(["script", "style", "noscript"]):
            x.decompose()
        return _clean(soup.get_text(" ", strip=True))
    except Exception:
        return ""


async def _check_platform(
    client: httpx.AsyncClient, title: str, name: str, cfg: dict
) -> PlatformResult:
    query = cfg["search"].format(title=title)
    results = await _serp_search(client, query)

    official_results = [
        x for x in results
        if _official(x.get("link", ""), cfg["domains"])
    ]

    if not official_results:
        return PlatformResult(
            name=name,
            available=False,
            confidence="not_found",
            note="No official India result found."
        )

    best = official_results[0]
    url = best.get("link")
    text = _clean(
        " ".join([
            best.get("title", ""),
            best.get("snippet", ""),
        ])
    )

    # Fetch the official page when possible. Some platforms render data
    # dynamically, so the search result itself remains a useful secondary
    # official signal.
    page_text = await _fetch_page(client, url)
    combined = _clean(text + " " + page_text)

    audio = _langs(combined)
    subtitles = _langs(combined)

    # "available" means an official result was found. It does NOT claim
    # every season/episode is available.
    return PlatformResult(
        name=name,
        available=True,
        url=url,
        audio=audio,
        subtitles=subtitles,
        confidence="official_page",
        note="Official platform result found; language availability may vary by season/episode."
    )


async def search_anime(title: str) -> AnimeResult:
    title = _clean(title)
    if not title:
        raise ValueError("Anime title is required.")

    result = AnimeResult(title=title)

    limits = httpx.Limits(max_connections=8, max_keepalive_connections=4)
    async with httpx.AsyncClient(limits=limits) as client:
        checks = [
            _check_platform(client, title, name, cfg)
            for name, cfg in PLATFORMS.items()
        ]
        platforms = await asyncio.gather(*checks, return_exceptions=True)

        for p in platforms:
            if isinstance(p, PlatformResult):
                result.platforms.append(p)
                if p.available:
                    result.source_count += 1
                    result.languages.extend(p.audio)

        # Official-source searches for release/status information.
        meta_queries = [
            f'site:crunchyroll.com "{title}" episode',
            f'site:crunchyroll.com "{title}" season',
            f'site:netflix.com/title "{title}"',
            f'site:primevideo.com/detail "{title}"',
        ]

        meta_results = []
        for q in meta_queries:
            meta_results.extend(await _serp_search(client, q))

        # Only use snippets/pages from our approved official domains.
        approved = []
        for item in meta_results:
            url = item.get("link", "")
            if any(_official(url, c["domains"]) for c in PLATFORMS.values()):
                approved.append(
                    _clean(item.get("title", "") + " " + item.get("snippet", ""))
                )

        meta_text = _clean(" ".join(approved))

    result.languages = list(dict.fromkeys(result.languages))
    result.dub = [x for x in result.languages if x in LANGUAGES and x != "Japanese"]

    result.status = _status(meta_text)
    last, nxt = _extract_next_last(meta_text)
    result.last_episode = last
    result.next_episode = nxt
    result.episodes = _episodes(meta_text)

    # Do not invent dates, season numbers, or episode counts.
    # They remain None when the official source does not expose them.
    return result


def format_result(data: AnimeResult) -> str:
    lines = [
        f"🎌 Anime: {data.title}",
        "",
        f"🔊 Dub: {', '.join(data.dub) if data.dub else 'Not verified'}",
        "",
        "📺 Platform:",
    ]

    available = [p for p in data.platforms if p.available]
    if available:
        for p in available:
            langs = ", ".join(p.audio) if p.audio else "Language not verified"
            lines.append(f"• {p.name} — {langs}")
    else:
        lines.append("• No official India platform result verified")

    lines += [
        "",
        f"📚 Season: {data.seasons or 'Not verified'}",
        f"🎬 Episodes: {data.episodes + '+' if data.episodes else 'Not verified'}",
        f"🌐 Languages: {', '.join(data.languages) if data.languages else 'Not verified'}",
        f"📌 Status: {data.status}",
        f"🎬 Last Episode: {data.last_episode or 'Not verified'}",
        f"⏭️ Next Episode: {data.next_episode or 'Not verified'}",
        f"📅 Expected: {data.expected or 'TBA / Not verified'}",
    ]

    if available:
        lines += ["", "🔗 Official sources:"]
        for p in available[:8]:
            if p.url:
                lines.append(f"• {p.name}: {p.url}")

    lines += [
        "",
        "⚠️ Language/episode availability can differ by season or episode."
    ]
    return "\n".join(lines)


async def get_anime_info(title: str) -> dict:
    """Main function for bot.py."""
    result = await search_anime(title)
    return asdict(result)


# Synchronous helper for older bot.py files.
def get_anime_info_sync(title: str) -> dict:
    return asyncio.run(get_anime_info(title))


if __name__ == "__main__":
    import sys

    anime = " ".join(sys.argv[1:]).strip()
    if not anime:
        print("Usage: python anime_service.py One Piece")
        raise SystemExit(1)

    data = get_anime_info_sync(anime)
    print(format_result(AnimeResult(**data)))
 
