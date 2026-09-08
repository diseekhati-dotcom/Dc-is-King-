"""
Verified anime metadata layer.

Important:
- Jikan/MAL is used only for neutral metadata (title, seasons, episodes,
  status, studio when available).
- Hindi-dub/platform claims are NOT inferred from MAL/Jikan.
- Platform adapters below are deliberately separated so each source can
  later be connected to an official/public API or an approved public page.
"""

from dataclasses import dataclass, field
from typing import List, Optional

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

async def find_anime(name: str) -> AnimeData:
    """
    Starter implementation.

    This intentionally does not pretend that a web page was checked.
    Connect official/public source adapters here before enabling claims
    about Hindi dubbing or platform availability.
    """
    title = name.strip().upper()

    # Neutral placeholder until the Jikan adapter is added.
    # Returning "Not verified" is safer than inventing data.
    return AnimeData(title=title)

def format_result(d: AnimeData) -> str:
    eps = str(d.episodes) if d.episodes is not None else "Not verified"
    langs = " • ".join(d.languages) if d.languages else "Not verified"
    last_ep = f"Episode {d.last_episode}" if d.last_episode else "Not verified"
    next_ep = f"Episode {d.next_episode}" if d.next_episode else "Not verified"

    return f"""🎬 Anime: {d.title}

🇮🇳 Hindi Dub: {"✅ Available" if d.hindi else "❌ Not verified"}
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
