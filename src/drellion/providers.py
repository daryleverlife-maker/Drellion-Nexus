from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol
import json
import shutil
import subprocess
import sys
import time
import urllib.parse

import requests


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


class AceStepHttpProvider:
    """ACE-Step 1.5 asynchronous API provider.

    Uses the documented /release_task -> /query_result -> /v1/audio flow.
    Source vocal is uploaded as src_audio and the first reference is uploaded as
    reference_audio. Additional reference blending remains a Drellion-side task.
    """

    id = "ace-step-http"
    name = "ACE-Step 1.5"

    def __init__(self, endpoint: str, api_key: str = "", poll_seconds: float = 2.0, timeout: float = 900.0):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.poll_seconds = max(0.5, poll_seconds)
        self.timeout = max(30.0, timeout)

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def status(self) -> ProviderStatus:
        if not self.endpoint:
            return ProviderStatus(self.id, self.name, ProviderState.DISABLED, "No endpoint configured", True, True, True, True)
        try:
            r = requests.get(f"{self.endpoint}/v1/stats", headers=self._headers(), timeout=3)
            if r.ok:
                return ProviderStatus(self.id, self.name, ProviderState.READY, self.endpoint, True, True, True, True)
            return ProviderStatus(self.id, self.name, ProviderState.OFFLINE, f"HTTP {r.status_code}", True, True, True, True)
        except requests.RequestException as exc:
            return ProviderStatus(self.id, self.name, ProviderState.OFFLINE, str(exc), True, True, True, True)

    @staticmethod
    def _task_id(payload: dict) -> str:
        data = payload.get("data", payload)
        task_id = data.get("task_id") or data.get("taskId")
        if not task_id:
            raise RuntimeError(f"ACE-Step did not return a task id: {payload}")
        return str(task_id)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        out = Path(request.output_dir or ".")
        out.mkdir(parents=True, exist_ok=True)
        files = {}
        handles = []
        try:
            vocal = Path(request.vocal_path)
            if vocal.is_file():
                handle = vocal.open("rb"); handles.append(handle)
                files["src_audio"] = (vocal.name, handle, "application/octet-stream")
            first_reference = Path(request.reference_paths[0]) if request.reference_paths else None
            if first_reference and first_reference.is_file():
                handle = first_reference.open("rb"); handles.append(handle)
                files["reference_audio"] = (first_reference.name, handle, "application/octet-stream")

            data = {
                "prompt": request.prompt,
                "lyrics": request.lyrics,
                "audio_duration": str(max(5.0, request.duration)),
                "task_type": "complete",
                "audio_cover_strength": "0.35",
            }
            if request.seed is not None:
                data["seed"] = str(request.seed)

            response = requests.post(
                f"{self.endpoint}/release_task",
                data=data,
                files=files or None,
                headers=self._headers(),
                timeout=60,
            )
            response.raise_for_status()
            task_id = self._task_id(response.json())
        finally:
            for handle in handles:
                handle.close()

        deadline = time.monotonic() + self.timeout
        result_payload = None
        while time.monotonic() < deadline:
            r = requests.post(
                f"{self.endpoint}/query_result",
                json={"task_ids": [task_id]},
                headers=self._headers(),
                timeout=30,
            )
            r.raise_for_status()
            payload = r.json()
            data = payload.get("data", payload)
            rows = data if isinstance(data, list) else data.get("results", data.get("tasks", [data]))
            row = rows[0] if isinstance(rows, list) and rows else rows
            status = int(row.get("status", 0)) if isinstance(row, dict) else 0
            if status == 1:
                result_payload = row
                break
            if status == 2:
                raise RuntimeError(f"ACE-Step generation failed: {row}")
            time.sleep(self.poll_seconds)

        if result_payload is None:
            raise TimeoutError("ACE-Step generation timed out.")

        candidates = result_payload.get("result") or result_payload.get("results") or result_payload.get("output") or []
        if isinstance(candidates, dict):
            candidates = [candidates]
        if not candidates:
            raise RuntimeError(f"ACE-Step returned no audio result: {result_payload}")

        first = candidates[0]
        if isinstance(first, str):
            remote_path = first
        else:
            remote_path = first.get("path") or first.get("audio_path") or first.get("audio")
        if not remote_path:
            raise RuntimeError(f"ACE-Step result has no audio path: {first}")

        target = out / "ace-step-generation.mp3"
        if str(remote_path).startswith(("http://", "https://")):
            audio_url = str(remote_path)
        else:
            audio_url = f"{self.endpoint}/v1/audio?path={urllib.parse.quote(str(remote_path), safe='')}"
        with requests.get(audio_url, headers=self._headers(), stream=True, timeout=120) as audio_response:
            audio_response.raise_for_status()
            with target.open("wb") as fh:
                for chunk in audio_response.iter_content(1024 * 1024):
                    if chunk:
                        fh.write(chunk)

        return GenerationResult(self.id, str(target), {}, request.seed, {"task_id": task_id, "raw": result_payload})


class DiffRhythmLocalProvider:
    id = "diffrhythm-local"
    name = "DiffRhythm 2 Local"

    def __init__(self, repo_path: str, python_executable: str = ""):
        self.repo_path = Path(repo_path)
        self.python_executable = python_executable or sys.executable

    def status(self) -> ProviderStatus:
        script = self.repo_path / "inference.py"
        available = self.repo_path.is_dir() and script.is_file() and Path(self.python_executable).exists()
        return ProviderStatus(
            self.id, self.name,
            ProviderState.READY if available else ProviderState.MISSING,
            str(self.repo_path) if available else "DiffRhythm2 repo/inference.py not configured",
            True, False, False, False,
        )

    @staticmethod
    def _lrc(lyrics: str, duration: float) -> str:
        lines = [line.strip() for line in lyrics.splitlines() if line.strip()]
        if not lines:
            lines = ["[Instrumental]"]
        step = max(1.0, duration / max(1, len(lines)))
        output = []
        for i, line in enumerate(lines):
            seconds = i * step
            minute = int(seconds // 60)
            second = seconds - minute * 60
            output.append(f"[{minute:02d}:{second:05.2f}] {line}")
        return "\n".join(output) + "\n"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        status = self.status()
        if status.state != ProviderState.READY:
            raise RuntimeError(status.detail)
        out = Path(request.output_dir or ".")
        out.mkdir(parents=True, exist_ok=True)

        lyrics_path = out / "diffrhythm-lyrics.lrc"
        lyrics_path.write_text(self._lrc(request.lyrics, request.duration), encoding="utf-8")
        style_prompt = request.reference_paths[0] if request.reference_paths else request.prompt
        song_name = f"drellion-diffrhythm-{request.seed or 0}"
        input_path = out / "diffrhythm-input.jsonl"
        input_path.write_text(json.dumps({
            "song_name": song_name,
            "lyrics": str(lyrics_path.resolve()),
            "style_prompt": str(Path(style_prompt).resolve()) if Path(style_prompt).is_file() else style_prompt,
        }) + "\n", encoding="utf-8")

        command = [
            self.python_executable,
            "inference.py",
            "--output-dir", str(out.resolve()),
            "--input-jsonl", str(input_path.resolve()),
            "--max-secs", str(max(10.0, request.duration)),
            "--steps", "16",
        ]
        result = subprocess.run(command, cwd=str(self.repo_path), capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr[-5000:] or result.stdout[-5000:] or "DiffRhythm generation failed.")
        target = out / f"{song_name}.mp3"
        if not target.is_file():
            matches = sorted(out.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not matches:
                raise RuntimeError("DiffRhythm finished without producing an MP3.")
            target = matches[0]
        return GenerationResult(self.id, str(target), {}, request.seed, {
            "stdout": result.stdout[-3000:],
            "reference_used": bool(request.reference_paths),
            "note": "DiffRhythm is a full-song generator; source-vocal preservation is not guaranteed.",
        })


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
