from __future__ import annotations

from pathlib import Path
from typing import Any

from .preferences import load_preferences, save_preferences


def recent_projects(limit: int = 20) -> list[dict[str, Any]]:
    prefs = load_preferences()
    items = prefs.get("recent_projects", []) or []
    clean = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "")
        if not path or path in seen:
            continue
        seen.add(path)
        clean.append({
            "path": path,
            "name": str(item.get("name", "") or Path(path).stem),
            "artist": str(item.get("artist", "") or ""),
            "updated_at": float(item.get("updated_at", 0.0) or 0.0),
        })
    return clean[:limit]


def register_recent(path: str | Path, *, name: str = "", artist: str = "", updated_at: float = 0.0) -> None:
    prefs = load_preferences()
    target = str(Path(path))
    items = [
        item for item in (prefs.get("recent_projects", []) or [])
        if isinstance(item, dict) and str(item.get("path", "")) != target
    ]
    items.insert(0, {
        "path": target,
        "name": name or Path(target).stem,
        "artist": artist,
        "updated_at": float(updated_at or 0.0),
    })
    prefs["recent_projects"] = items[:30]
    save_preferences(prefs)


def remove_recent(path: str | Path) -> None:
    prefs = load_preferences()
    target = str(Path(path))
    prefs["recent_projects"] = [
        item for item in (prefs.get("recent_projects", []) or [])
        if isinstance(item, dict) and str(item.get("path", "")) != target
    ]
    save_preferences(prefs)
