"""
anime_service.py
Official-source-only anime information checker.

IMPORTANT:
- This service never searches, opens, or uses unofficial anime streaming/download sites.
- Facts are accepted only from the approved official platform domains below.
- A platform is NOT marked verified merely because a generic search result exists:
  the result must contain the requested anime title (or a strong title match).
- Missing information is returned as "Not verified" instead of being guessed.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


BUILD_ID = "official-v3"
INDIA = "India"

# Only these domains are allowed as evidence.
PLATFORMS = {
    "Crunchyroll": {
        "domains": ["crunchyroll.com"],
        "query": 'site:crunchyroll.com/series/ "{title}"',
    },
    "Netflix": {
        "domains": ["netflix.com"],
        "query": 'site:netflix.com/title/ "{title}"',
    },
    "Amazon Prime Video": {
        "domains": ["primevideo.com"],
        "query": 'site:primevideo.com/detail/ "{title}"',
    },
    "Disney+": {
        "domains": ["disneyplus.com"],
        "query": 'site:disneyplus.com "{title}"',
    },
    "JioHotstar": {
        "domains": ["hotstar.com", "jiohotstar.com"],
        "query": 'site:hotstar.com "{title}" anime',
    },
    "JioCinema": {
        "domains": ["jiocinema.com"],
        "query": 'site:jiocinema.com "{title}" anime',
    },
    "Sony YAY!": {
        "domains": ["sonyyay.com", "sonypicturesnetworks.com"],
        "query": 'site:sonyyay.com "{title}" anime',
    },
    "SonyLIV": {
        "domains": ["sonyliv.com"],
        "query": 'site:sonyliv.com "{title}" anime',
    },
    "MX Player": {
        "domains": ["mxplayer.in", "amazon.com"],
        "query": 'site:mxplayer.in "{title}" anime',
    },
    "YouTube": {
        "domains": ["youtube.com"],
        "query": 'site:youtube.com "{title}" anime official',
    },
    "Muse India": {
        "domains": ["youtube.com", "museindia.in"],
        "query": 'site:youtube.com/@MuseIndia "{title}"',
    },
    "Ani-One Asia": {
        "domains": ["youtube.com", "ani-one.com"],
        "query": 'site:youtube.com "{title}" "Ani-One" India',
    },
    "Animax": {
        "domains": ["animax-asia.com", "sony-asia.com"],
        "query": 'site:animax-asia.com "{title}"',
    },
    "Cartoon Network": {
        "domains": ["cartoonnetworkasia.com", "cartoonnetwork.com"],
        "query": 'site:cartoonnetworkasia.com "{title}" anime',
    },
    "Nickelodeon": {
        "domains": ["nick.com", "nickelodeon.com"],
        "query": 'site:nick.com "{title}" anime',
    },
}

LANGUAGES = [
    "Hindi", "English", "Japanese", "Tamil", "Telugu", "Malayalam",
    "Kannada", "Bengali", "Marathi", "Korean", "Chinese", "Thai",
    "Spanish", "French", "German", "Portuguese", "Arabic",
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


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _official(url: str, domains: list[str]) -> bool:
    host = _host(url)
    return any(host == d or host.endswith("." + d) for d in domains)


def _normalize_title(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return _clean(text)


def _title_match(query_title: str, result_title: str, snippet: str) -> bool:
    wanted = _normalize_title(query_title)
    haystack = _normalize_title(f"{result_title} {snippet}")

    if not wanted or wanted not in haystack:
        # Allow token matching for punctuation/colon differences.
        tokens = [x for x in wanted.split() if len(x) > 1]
        if not tokens or not all(x in haystack.split() for x in tokens):
            return False

    return True


def _find_languages(text: str) -> list[str]:
    """Extract languages only from likely audio/subtitle language sections."""
    clean = _clean(text)
    low = clean.lower()
    chunks: list[str] = []

    markers = [
        "audio languages", "audio language", "audio:",
        "dub languages", "dub language", "dub:",
        "languages:", "language:",
        "subtitles", "subtitle",
    ]

    for marker in markers:
        start = 0
        while True:
            pos = low.find(marker, start)
            if pos < 0:
                break
            chunks.append(clean[pos:pos + 350])
            start = pos + len(marker)

    # If no labelled section exists, do not treat every occurrence of
    # "English/Japanese/etc." on the page as an audio track.
    if not chunks:
        return []

    found: list[str] = []
    for chunk in chunks:
        low_chunk = chunk.lower()
        for lang in LANGUAGES:
            if re.search(rf"\b{re.escape(lang.lower())}\b", low_chunk):
                if lang not in found:
                    found.append(lang)

    return found


def _extract_episode_count(text: str) -> Optional[int]:
    patterns = [
        r"\b(\d{1,4})\s+episodes?\b",
        r"\bepisodes?\s*[:\-]?\s*(\d{1,4})\b",
    ]
    nums: list[int] = []
    for pattern in patterns:
        nums.extend(int(x) for x in re.findall(pattern, text, re.I))
    return max(nums) if nums else None


def _extract_episode_numbers(text: str) -> list[int]:
    nums = re.findall(r"\b(?:episode|ep\.?)\s*(\d{1,4})\b", text, re.I)
    return [int(x) for x in nums]


def _extract_season(text: str) -> Optional[str]:
    matches = re.findall(r"\bseason\s+(\d{1,2})\b", text, re.I)
    if matches:
        return max(matches, key=int)
    return None


def _status(text: str) -> str:
    low = text.lower()
    if any(x in low for x in [
        "currently airing", "ongoing", "simulcast", "new episode",
        "airing now", "weekly",
    ]):
        return "Ongoing"
    if any(x in low for x in [
        "completed", "complete series", "all episodes available",
        "all episodes",
    ]):
        return "Completed"
    if any(x in low for x in ["upcoming", "coming soon", "premieres"]):
        return "Upcoming"
    return "Unknown"


def _explicit_next_episode(text: str) -> Optional[str]:
    patterns = [
        r"next episode\s*(?:is|:|-)?\s*(?:episode|ep\.?)?\s*(\d{1,4})",
        r"episode\s*(\d{1,4})\s*(?:is\s+)?(?:next|up next)",
        r"up next\s*(?:is|:|-)?\s*(?:episode|ep\.?)?\s*(\d{1,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return f"Episode {int(match.group(1))}"
    return None


def _explicit_last_episode(text: str) -> Optional[str]:
    patterns = [
        r"last episode\s*(?:is|:|-)?\s*(?:episode|ep\.?)?\s*(\d{1,4})",
        r"latest episode\s*(?:is|:|-)?\s*(?:episode|ep\.?)?\s*(\d{1,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return f"Episode {int(match.group(1))}"
    return None


async def _serp_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    key = os.getenv("SERPAPI_KEY", "").strip()
    if not key:
        return []

    try:
        response = await client.get(
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
        response.raise_for_status()
        data = response.json()
        return data.get("organic_results", []) or []
    except Exception:
        return []


async def _fetch_page(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await client.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; AnimeInfoBot/3.0; +Telegram)"
                )
            },
            timeout=20,
            follow_redirects=True,
        )
        if response.status_code >= 400:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        return _clean(soup.get_text(" ", strip=True))
    except Exception:
        return ""


async def _check_platform(
    client: httpx.AsyncClient,
    title: str,
    name: str,
    cfg: dict,
) -> PlatformResult:
    results = await _serp_search(
        client, cfg["query"].format(title=title)
    )

    for item in results:
        url = item.get("link", "")
        result_title = item.get("title", "")
        snippet = item.get("snippet", "")

        if not _official(url, cfg["domains"]):
            continue

        if not _title_match(title, result_title, snippet):
            continue

        page_text = await _fetch_page(client, url)
        combined = _clean(f"{result_title} {snippet} {page_text}")

        audio = _find_languages(combined)

        # We intentionally do not label the same broad text as both audio
        # and subtitles. Only audio is used for "Dub".
        episode_count = _extract_episode_count(combined)
        season = _extract_season(combined)
        status = _status(combined)

        notes = ["Exact/strong official title match found."]
        if audio:
            notes.append("Audio language evidence found on/near official page.")
        else:
            notes.append("Audio language not verified.")
        if episode_count:
            notes.append(f"Official text indicates {episode_count} episodes.")
        if season:
            notes.append(f"Official text indicates Season {season}.")
        if status != "Unknown":
            notes.append(f"Official text indicates {status}.")

        return PlatformResult(
            name=name,
            available=True,
            url=url,
            audio=audio,
            subtitles=[],
            confidence="official_title_match",
            note=" ".join(notes),
        )

    return PlatformResult(
        name=name,
        available=False,
        confidence="not_verified",
        note="No matching official India result was verified.",
    )


async def search_anime(title: str) -> AnimeResult:
    title = _clean(title)
    if not title:
        raise ValueError("Anime title is required.")

    result = AnimeResult(title=title)

    limits = httpx.Limits(max_connections=8, max_keepalive_connections=4)

    async with httpx.AsyncClient(
        limits=limits,
        follow_redirects=True,
    ) as client:
        checks = [
            _check_platform(client, title, name, cfg)
            for name, cfg in PLATFORMS.items()
        ]
        checked = await asyncio.gather(*checks, return_exceptions=True)

        for item in checked:
            if not isinstance(item, PlatformResult):
                continue

            result.platforms.append(item)

            if item.available:
                result.source_count += 1
                result.languages.extend(item.audio)

        # Use official platform evidence for overall metadata.
        evidence_parts: list[str] = []
        for platform in result.platforms:
            if platform.available:
                evidence_parts.append(platform.note)

        # Also do a small set of official-only metadata searches.
        meta_queries = [
            f'site:crunchyroll.com "{title}" "Episode"',
            f'site:primevideo.com/detail "{title}"',
            f'site:netflix.com/title "{title}"',
        ]

        for query in meta_queries:
            for item in await _serp_search(client, query):
                url = item.get("link", "")
                if not any(
                    _official(url, cfg["domains"])
                    for cfg in PLATFORMS.values()
                ):
                    continue

                snippet = _clean(
                    f'{item.get("title", "")} {item.get("snippet", "")}'
                )
                if _title_match(title, item.get("title", ""), item.get("snippet", "")):
                    evidence_parts.append(snippet)

        evidence = _clean(" ".join(evidence_parts))

    result.languages = list(dict.fromkeys(result.languages))
    result.dub = [
        language for language in result.languages
        if language != "Japanese"
    ]

    result.status = _status(evidence)
    result.seasons = _extract_season(evidence)

    count = _extract_episode_count(evidence)
    result.episodes = str(count) if count is not None else None

    result.last_episode = _explicit_last_episode(evidence)
    result.next_episode = _explicit_next_episode(evidence)

    # Never guess "next = last + 1".
    # Never invent release/expected dates.
    result.expected = None

    return result


def format_result(data: AnimeResult) -> str:
    lines = [
        f"🎌 Anime: {data.title}",
        "",
        f"🔊 Dub: {', '.join(data.dub) if data.dub else 'Not verified'}",
        "",
        "📺 Official/Authorized Platforms:",
    ]

    available = [p for p in data.platforms if p.available]

    if available:
        for platform in available:
            languages = (
                ", ".join(platform.audio)
                if platform.audio
                else "Audio language not verified"
            )
            lines.append(f"• {platform.name} — {languages}")
    else:
        lines.append("• No official India platform verified")

    lines.extend([
        "",
        f"📚 Season: {data.seasons or 'Not verified'}",
        f"🎬 Episodes: {data.episodes or 'Not verified'}",
        f"🌐 Languages: {', '.join(data.languages) if data.languages else 'Not verified'}",
        f"📌 Status: {data.status}",
        f"🎬 Last Episode: {data.last_episode or 'Not verified'}",
        f"⏭️ Next Episode: {data.next_episode or 'Not verified'}",
        f"📅 Expected: {data.expected or 'TBA / Not verified'}",
    ])

    if available:
        lines.extend(["", "🔗 Verified official pages:"])
        for platform in available[:8]:
            if platform.url:
                lines.append(f"• {platform.name}: {platform.url}")

    lines.extend([
        "",
        "ℹ️ Data is shown only when it can be verified from an approved official/authorized source.",
        f"🛠 Build: {BUILD_ID}",
    ])

    return "\n".join(lines)


async def get_anime_info(title: str) -> dict:
    return asdict(await search_anime(title))


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
    
 
