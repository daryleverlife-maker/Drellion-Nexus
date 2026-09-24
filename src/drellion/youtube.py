from __future__ import annotations

from dataclasses import dataclass
import requests


@dataclass
class YouTubeReference:
    url: str
    title: str = ""
    author: str = ""
    thumbnail_url: str = ""
    html: str = ""


def fetch_oembed(url: str, timeout: float = 5.0) -> YouTubeReference:
    """Fetch public YouTube oEmbed metadata without downloading media."""
    if not url.strip():
        raise ValueError("YouTube URL is required.")
    response = requests.get(
        "https://www.youtube.com/oembed",
        params={"url": url.strip(), "format": "json"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return YouTubeReference(
        url=url.strip(),
        title=str(data.get("title", "")),
        author=str(data.get("author_name", "")),
        thumbnail_url=str(data.get("thumbnail_url", "")),
        html=str(data.get("html", "")),
    )
