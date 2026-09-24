from __future__ import annotations

import json
import urllib.parse
import urllib.request


def youtube_oembed(url: str, timeout: float = 5.0) -> dict[str, str]:
    value = (url or '').strip()
    if not value:
        return {}
    endpoint = 'https://www.youtube.com/oembed?' + urllib.parse.urlencode({
        'url': value,
        'format': 'json',
    })
    request = urllib.request.Request(endpoint, headers={'User-Agent': 'Drellion-Nexus/2'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
        return {
            'title': str(payload.get('title', '') or ''),
            'artist': str(payload.get('author_name', '') or ''),
            'thumbnail_url': str(payload.get('thumbnail_url', '') or ''),
        }
    except Exception:
        return {}
