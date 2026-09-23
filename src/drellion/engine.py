from dataclasses import dataclass
from pathlib import Path
from .project import ProjectState
from .audio.contracts import VocalAnalysis, ReferenceAnalysis

@dataclass
class BuildResult:
    build_path: str
    instrumental_path: str = ""
    report_path: str = ""

class NexusEngine:
    """Stable boundary between the UI/project model and audio backends."""
    def analyze_vocal(self, state: ProjectState) -> VocalAnalysis:
        if not state.vocal.path:
            raise ValueError("A vocal stem is required for vocal-first generation.")
        return VocalAnalysis()

    def analyze_reference(self, state: ProjectState) -> ReferenceAnalysis:
        if not state.reference.path:
            raise ValueError("A reference track is required.")
        return ReferenceAnalysis()

    def generate_previews(self, state: ProjectState, output_dir: str | Path):
        raise NotImplementedError("Arrangement generation backend is not wired yet.")

    def build(self, state: ProjectState, output_dir: str | Path) -> BuildResult:
        raise NotImplementedError("Full build backend is not wired yet.")

    def master(self, state: ProjectState, output_dir: str | Path) -> str:
        raise NotImplementedError("Mastering backend is not wired yet.")
