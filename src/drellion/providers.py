from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol
import shutil
import urllib.request


class ProviderState(str, Enum):
    READY = "ready"
    MISSING = "missing"
    OFFLINE = "offline"
    DISABLED = "disabled"


@dataclass
class ProviderStatus:
    id: str
    name: str
    state: ProviderState
    detail: str = ""
    supports_reference: bool = False
    supports_source_audio: bool = False
    supports_stems: bool = False
    remote: bool = False


@dataclass
class GenerationRequest:
    vocal_path: str
    lyrics: str
    reference_paths: list[str]
    prompt: str
    duration: float
    seed: int | None = None
    output_dir: str = ""
    source_roles: dict[str, str] | None = None


@dataclass
class GenerationResult:
    provider_id: str
    audio_path: str
    stems: dict[str, str]
    seed: int | None
    metadata: dict


class MusicProvider(Protocol):
    id: str
    name: str

    def status(self) -> ProviderStatus: ...
    def generate(self, request: GenerationRequest) -> GenerationResult: ...


class HttpProvider:
    def __init__(self, provider_id: str, name: str, endpoint: str, *, reference=True, source=True):
        self.id = provider_id
        self.name = name
        self.endpoint = endpoint.rstrip("/")
        self._reference = reference
        self._source = source

    def status(self) -> ProviderStatus:
        if not self.endpoint:
            return ProviderStatus(self.id, self.name, ProviderState.DISABLED, "No endpoint configured", self._reference, self._source, True, True)
        try:
            req = urllib.request.Request(self.endpoint, method="HEAD")
            with urllib.request.urlopen(req, timeout=2):
                pass
            state, detail = ProviderState.READY, self.endpoint
        except Exception:
            state, detail = ProviderState.OFFLINE, self.endpoint
        return ProviderStatus(self.id, self.name, state, detail, self._reference, self._source, True, True)


class LocalCommandProvider:
    def __init__(self, provider_id: str, name: str, executable: str, *, reference=True, source=True):
        self.id = provider_id
        self.name = name
        self.executable = executable
        self._reference = reference
        self._source = source

    def status(self) -> ProviderStatus:
        path = shutil.which(self.executable) or (self.executable if Path(self.executable).is_file() else "")
        state = ProviderState.READY if path else ProviderState.MISSING
        return ProviderStatus(self.id, self.name, state, path or f"{self.executable} not installed", self._reference, self._source, True, False)


class EngineBroker:
    """Central provider registry. Never silently falls back between providers."""

    def __init__(self):
        self.providers: dict[str, object] = {}

    def register(self, provider) -> None:
        self.providers[provider.id] = provider

    def statuses(self) -> list[ProviderStatus]:
        return [provider.status() for provider in self.providers.values()]

    def choose(self, preferred: str | None = None):
        if preferred and preferred != "auto":
            provider = self.providers.get(preferred)
            if provider is None:
                raise ValueError(f"Unknown engine: {preferred}")
            status = provider.status()
            if status.state != ProviderState.READY:
                raise RuntimeError(f"{status.name} is not ready: {status.detail}")
            return provider
        for provider in self.providers.values():
            if provider.status().state == ProviderState.READY:
                return provider
        raise RuntimeError("No music-generation engine is ready. Drellion will not silently use the Basic Test Engine.")
