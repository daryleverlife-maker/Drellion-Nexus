from dataclasses import dataclass, field

@dataclass
class VocalAnalysis:
    duration: float = 0.0
    phrase_regions: list[tuple[float, float]] = field(default_factory=list)
    pitch_track: list[tuple[float, float]] = field(default_factory=list)

@dataclass
class ReferenceAnalysis:
    bpm: float = 0.0
    duration: float = 0.0
    energy_curve: list[float] = field(default_factory=list)
    groove: dict[str, float] = field(default_factory=dict)
    tone: dict[str, float] = field(default_factory=dict)
    stereo: dict[str, float] = field(default_factory=dict)
    dynamics: dict[str, float] = field(default_factory=dict)

@dataclass
class ArrangementPreview:
    name: str
    audio_path: str
    description: str
    similarity: dict[str, float] = field(default_factory=dict)
