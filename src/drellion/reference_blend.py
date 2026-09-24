from __future__ import annotations

from dataclasses import dataclass, field
from .project import ReferenceAsset


@dataclass
class ReferenceBlend:
    weights: dict[str, float] = field(default_factory=dict)
    dimensions: dict[str, dict[str, float]] = field(default_factory=dict)


def normalize_references(references: list[ReferenceAsset]) -> ReferenceBlend:
    active = [r for r in references if r.enabled and (r.path or r.youtube_url)]
    total = sum(max(0.0, r.weight) for r in active)
    if total <= 0 and active:
        total = float(len(active))
        raw = {r.id: 1.0 for r in active}
    else:
        raw = {r.id: max(0.0, r.weight) for r in active}

    weights = {key: value / total for key, value in raw.items()} if total else {}
    dimensions: dict[str, dict[str, float]] = {}
    for dimension in ("drums","bass","energy","arrangement","tone","stereo","master"):
        d = {}
        subtotal = 0.0
        for r in active:
            value = weights.get(r.id, 0.0) * max(0.0, float(r.influences.get(dimension, 0.0)))
            if value:
                d[r.id] = value
                subtotal += value
        dimensions[dimension] = {k: v/subtotal for k,v in d.items()} if subtotal else {}
    return ReferenceBlend(weights, dimensions)
