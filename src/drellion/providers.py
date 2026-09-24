from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol
import base64
import json
import shutil
import subprocess
import tempfile
import time

import requests


@dataclass(frozen=True)
class EngineStatus:
    name: str
    ready: bool
    detail: str = ""
    version: str = ""
    mode: str = ""


@dataclass
class GenerationRequest:
    source_audio: str
    reference_audio: list[str] = field(default_factory=list)
    prompt: str = ""
    lyrics: str = ""
    seed: int = 0
    duration_seconds: float | None = None
    start_seconds: float = 0.0
    task: str = "complete"
    reference_strength: float = 0.55
    output_dir: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    engine: str
    engine_version: str
    audio_path: str
    stems: dict[str, str] = field(default_factory=dict)
    seed: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class GenerationProvider(Protocol):
    name: str
    def status(self) -> EngineStatus: ...
    def generate(self, request: GenerationRequest, progress: Callable[[str], None] | None = None) -> GenerationResult: ...


def _file_to_data_url(path: str | Path) -> str:
    p = Path(path)
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:audio/wav;base64,{encoded}"


def _download(session: requests.Session, url: str, destination: Path, timeout: int = 180) -> Path:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


class AceStepHttpProvider:
    name = "ACE-Step"

    def __init__(self, base_url: str, timeout: int = 30, poll_seconds: float = 1.5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_seconds = poll_seconds
        self.session = requests.Session()

    def status(self) -> EngineStatus:
        if not self.base_url:
            return EngineStatus(self.name, False, "Endpoint not configured", mode="HTTP")
        try:
            models = self.session.get(f"{self.base_url}/v1/models", timeout=min(self.timeout, 8))
            if models.status_code < 400:
                payload = models.json() if "json" in models.headers.get("content-type", "") else {}
                data = payload.get("data", payload) if isinstance(payload, dict) else {}
                default_model = str(data.get("default_model") or data.get("loaded_model") or "") if isinstance(data, dict) else ""
                detail = f"Ready · {default_model}" if default_model else "Ready"
                return EngineStatus(self.name, True, detail, version=default_model, mode="HTTP")
            response = self.session.get(f"{self.base_url}/v1/stats", timeout=min(self.timeout, 8))
            if response.status_code == 404:
                response = self.session.get(f"{self.base_url}/health", timeout=min(self.timeout, 8))
            response.raise_for_status()
            payload = response.json() if "json" in response.headers.get("content-type", "") else {}
            data = payload.get("data", payload) if isinstance(payload, dict) else {}
            version = str(data.get("version") or data.get("model") or "") if isinstance(data, dict) else ""
            return EngineStatus(self.name, True, "Ready", version=version, mode="HTTP")
        except Exception as exc:
            return EngineStatus(self.name, False, str(exc), mode="HTTP")

    def _ensure_base_model_for_complete(self, progress: Callable[[str], None] | None = None) -> str:
        """Return a base-model name suitable for ACE-Step's Complete task.

        ACE-Step documents Complete/Lego/Extract as base-model-only tasks. If
        the API is currently running Turbo, initialize the base model on demand
        through /v1/init rather than generating invalid candidates repeatedly.
        """
        wanted = "acestep-v15-base"
        try:
            response = self.session.get(f"{self.base_url}/v1/models", timeout=min(self.timeout, 12))
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else {}
            models = data.get("models", []) if isinstance(data, dict) else []
            for model in models if isinstance(models, list) else []:
                if not isinstance(model, dict):
                    continue
                name = str(model.get("name") or "")
                if "base" in name.lower() and (model.get("is_loaded") is not False):
                    return name
        except Exception:
            pass

        if progress:
            progress("Preparing ACE-Step base model for vocal completion")
        try:
            response = self.session.post(
                f"{self.base_url}/v1/init",
                json={"model": wanted, "slot": 1, "init_llm": False},
                timeout=max(self.timeout, 900),
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and payload.get("error"):
                raise RuntimeError(str(payload["error"]))
            data = payload.get("data", payload) if isinstance(payload, dict) else {}
            loaded = str(data.get("loaded_model") or wanted) if isinstance(data, dict) else wanted
            if "base" not in loaded.lower():
                raise RuntimeError(f"ACE-Step initialized {loaded!r}, but Complete requires a base model")
            return loaded
        except Exception as exc:
            raise RuntimeError(
                "ACE-Step Complete requires the acestep-v15-base model. "
                "Drellion could not switch the API server to the base model automatically. "
                "Set ACESTEP_CONFIG_PATH=acestep-v15-base (or initialize that model in ACE-Step) "
                f"and restart the API server. Details: {exc}"
            ) from exc

    def generate(self, request: GenerationRequest, progress: Callable[[str], None] | None = None) -> GenerationResult:
        if not self.status().ready:
            raise RuntimeError(f"{self.name} endpoint is unavailable at {self.base_url}")
        out_dir = Path(request.output_dir or tempfile.mkdtemp(prefix="drellion-ace-"))
        out_dir.mkdir(parents=True, exist_ok=True)
        if progress:
            progress("Submitting to ACE-Step")

        data: dict[str, Any] = {
            "task_type": request.task,
            "prompt": request.prompt,
            "lyrics": request.lyrics,
            "seed": str(int(request.seed)),
            "use_random_seed": "false",
            "audio_format": "wav",
            "audio_cover_strength": str(float(request.reference_strength)),
        }
        if request.duration_seconds is not None:
            data["audio_duration"] = str(float(request.duration_seconds))
        if request.task == "complete":
            base_model = self._ensure_base_model_for_complete(progress)
            track_classes = ["drums", "bass", "guitar", "keyboard", "synth", "strings", "percussion", "fx"]
            data["model"] = base_model
            data["track_classes"] = track_classes
            data["instruction"] = "Complete the input track with " + " | ".join(x.upper() for x in track_classes) + ":"
            data["thinking"] = "false"
            data["inference_steps"] = "50"
        elif request.task in {"text2music", "lego"}:
            data["thinking"] = "true"

        handles: list[Any] = []
        files: dict[str, Any] = {}
        try:
            source_path = Path(request.source_audio)
            source_handle = source_path.open("rb")
            handles.append(source_handle)
            files["src_audio"] = (source_path.name, source_handle, "application/octet-stream")
            refs = [Path(x) for x in request.reference_audio if x and Path(x).exists()]
            if refs:
                ref_handle = refs[0].open("rb")
                handles.append(ref_handle)
                files["reference_audio"] = (refs[0].name, ref_handle, "application/octet-stream")

            response = self.session.post(
                f"{self.base_url}/release_task",
                data=data,
                files=files,
                timeout=max(self.timeout, 120),
            )
            response.raise_for_status()
        finally:
            for handle in handles:
                try:
                    handle.close()
                except Exception:
                    pass

        created = response.json()
        created_data = created.get("data", created) if isinstance(created, dict) else created
        task_id = None
        if isinstance(created_data, dict):
            task_id = created_data.get("task_id") or created_data.get("id")
        elif isinstance(created_data, str):
            task_id = created_data
        if not task_id:
            raise RuntimeError(f"ACE-Step did not return a task id: {created}")

        deadline = time.monotonic() + max(180.0, (request.duration_seconds or 30.0) * 12.0)
        result_payload: Any = None
        while time.monotonic() < deadline:
            if progress:
                progress("ACE-Step is generating")
            q = self.session.post(
                f"{self.base_url}/query_result",
                json={"task_id_list": [str(task_id)]},
                timeout=self.timeout,
            )
            q.raise_for_status()
            payload = q.json()
            if isinstance(payload, dict) and payload.get("error"):
                raise RuntimeError(str(payload["error"]))
            entries = payload.get("data", payload) if isinstance(payload, dict) else payload
            if isinstance(entries, dict):
                entries = [entries]
            entry = entries[0] if isinstance(entries, list) and entries else {}
            if not isinstance(entry, dict):
                entry = {}
            state = entry.get("status")
            if state in (2, "2", "failed", "error", "cancelled"):
                raise RuntimeError(str(entry.get("error") or entry.get("message") or entry))
            if state in (1, "1", "success", "completed", "done", "finished"):
                result_payload = entry
                break
            time.sleep(self.poll_seconds)

        if result_payload is None:
            raise TimeoutError("ACE-Step generation timed out")

        audio_url = _extract_audio_url(result_payload)
        audio_path = out_dir / f"ace-{request.seed}.wav"
        if not audio_url:
            raise RuntimeError(f"ACE-Step result did not contain an audio URL: {result_payload}")
        if audio_url.startswith("data:"):
            encoded = audio_url.split(",", 1)[1]
            audio_path.write_bytes(base64.b64decode(encoded))
        else:
            if audio_url.startswith("/"):
                audio_url = self.base_url + audio_url
            _download(self.session, audio_url, audio_path)
        status = self.status()
        return GenerationResult(self.name, status.version, str(audio_path), seed=request.seed, metadata={"task_id": str(task_id)})


def _extract_audio_url(payload: Any) -> str | None:
    if isinstance(payload, str):
        stripped = payload.strip()
        if stripped.startswith(("http://", "https://", "/", "data:")):
            return stripped
        if stripped.startswith(("[", "{")):
            try:
                return _extract_audio_url(json.loads(stripped))
            except json.JSONDecodeError:
                return None
        return None
    if isinstance(payload, list):
        for item in payload:
            found = _extract_audio_url(item)
            if found:
                return found
        return None
    if isinstance(payload, dict):
        for key in ("audio_url", "url", "audio", "file", "path"):
            value = payload.get(key)
            found = _extract_audio_url(value)
            if found:
                return found
        for key in ("result", "data", "outputs", "output", "files"):
            found = _extract_audio_url(payload.get(key))
            if found:
                return found
    return None


class DiffRhythmHttpProvider:
    name = "DiffRhythm"

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def status(self) -> EngineStatus:
        if not self.base_url:
            return EngineStatus(self.name, False, "Endpoint not configured", mode="HTTP")
        for endpoint in ("/health", "/v1/stats", "/"):
            try:
                response = self.session.get(self.base_url + endpoint, timeout=min(self.timeout, 8))
                if response.status_code < 500:
                    return EngineStatus(self.name, True, f"Reachable ({response.status_code})", mode="HTTP")
            except Exception:
                pass
        return EngineStatus(self.name, False, "Endpoint unavailable", mode="HTTP")

    def generate(self, request: GenerationRequest, progress: Callable[[str], None] | None = None) -> GenerationResult:
        if not self.status().ready:
            raise RuntimeError("DiffRhythm endpoint is unavailable")
        if progress:
            progress("Submitting to DiffRhythm")
        files = {"source_audio": open(request.source_audio, "rb")}
        try:
            if request.reference_audio:
                files["reference_audio"] = open(request.reference_audio[0], "rb")
            data = {
                "prompt": request.prompt,
                "lyrics": request.lyrics,
                "seed": str(request.seed),
                "duration": str(request.duration_seconds or ""),
            }
            response = self.session.post(f"{self.base_url}/generate", files=files, data=data, timeout=max(self.timeout, 600))
            response.raise_for_status()
            out_dir = Path(request.output_dir or tempfile.mkdtemp(prefix="drellion-diff-"))
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f"diffrhythm-{request.seed}.wav"
            ctype = response.headers.get("content-type", "")
            if "audio" in ctype or not "json" in ctype:
                out.write_bytes(response.content)
            else:
                payload = response.json()
                url = _extract_audio_url(payload)
                if not url:
                    raise RuntimeError(f"DiffRhythm result did not contain audio: {payload}")
                if url.startswith("/"):
                    url = self.base_url + url
                _download(self.session, url, out)
            return GenerationResult(self.name, "", str(out), seed=request.seed)
        finally:
            for handle in files.values():
                try: handle.close()
                except Exception: pass


class DiffRhythmLocalProvider:
    name = "DiffRhythm Local"

    def __init__(self, repo_dir: str, python_executable: str | None = None) -> None:
        self.repo_dir = Path(repo_dir) if repo_dir else Path()
        self.python = python_executable or shutil.which("python") or "python"

    def status(self) -> EngineStatus:
        inference = self.repo_dir / "inference.py"
        return EngineStatus(self.name, inference.exists(), str(inference) if inference.exists() else "inference.py not found", mode="Local")

    def generate(self, request: GenerationRequest, progress: Callable[[str], None] | None = None) -> GenerationResult:
        if not self.status().ready:
            raise RuntimeError("DiffRhythm local repository is not configured")
        out_dir = Path(request.output_dir or tempfile.mkdtemp(prefix="drellion-diff-local-"))
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"diffrhythm-local-{request.seed}.wav"
        command = [
            self.python, str(self.repo_dir / "inference.py"),
            "--audio", request.source_audio, "--output", str(out),
            "--seed", str(request.seed), "--prompt", request.prompt,
        ]
        if request.reference_audio:
            command += ["--ref_audio", request.reference_audio[0]]
        if request.lyrics:
            lyrics_file = out_dir / f"lyrics-{request.seed}.txt"
            lyrics_file.write_text(request.lyrics, encoding="utf-8")
            command += ["--lyrics", str(lyrics_file)]
        if progress: progress("Running DiffRhythm locally")
        proc = subprocess.run(command, cwd=self.repo_dir, capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "DiffRhythm failed")
        if not out.exists():
            raise RuntimeError("DiffRhythm completed without creating the expected output")
        return GenerationResult(self.name, "", str(out), seed=request.seed)


class BasicTestEngine:
    name = "Basic Test Engine"

    def status(self) -> EngineStatus:
        return EngineStatus(self.name, True, "Developer/demo quality only", mode="Explicit fallback")

    def generate(self, request: GenerationRequest, progress: Callable[[str], None] | None = None) -> GenerationResult:
        from .audio_core import read_wav, write_wav
        import numpy as np
        source = read_wav(request.source_audio)
        duration = request.duration_seconds or min(30.0, source.duration)
        n = max(1, int(duration * source.sample_rate))
        rng = np.random.default_rng(request.seed)
        t = np.arange(n, dtype=np.float32) / source.sample_rate
        kick = np.sin(2 * np.pi * 55 * t) * ((np.mod(t, 0.5) < 0.08).astype(np.float32)) * 0.12
        noise = rng.normal(0, 0.015, n).astype(np.float32) * (np.mod(t + 0.25, 0.5) < 0.04)
        out = (kick + noise)[:, None]
        out_dir = Path(request.output_dir or tempfile.mkdtemp(prefix="drellion-basic-"))
        out_dir.mkdir(parents=True, exist_ok=True)
        path = write_wav(out_dir / f"basic-{request.seed}.wav", out, source.sample_rate)
        return GenerationResult(self.name, "2.0-test", str(path), seed=request.seed, metadata={"warning":"demonstration quality"})


class EngineBroker:
    def __init__(self, providers: list[GenerationProvider], explicit_basic: bool = False) -> None:
        self.providers = providers
        self.explicit_basic = explicit_basic

    def statuses(self) -> list[EngineStatus]:
        statuses = [p.status() for p in self.providers]
        statuses.append(BasicTestEngine().status())
        return statuses

    def ready_provider(self, preferred: str | None = None) -> GenerationProvider:
        if preferred == BasicTestEngine.name:
            if not self.explicit_basic:
                raise RuntimeError("Basic Test Engine requires explicit opt-in")
            return BasicTestEngine()
        if preferred:
            for provider in self.providers:
                if provider.name == preferred:
                    status = provider.status()
                    if not status.ready:
                        raise RuntimeError(f"{preferred} is not ready: {status.detail}")
                    return provider
            raise RuntimeError(f"Unknown generation engine: {preferred}")
        for provider in self.providers:
            if provider.status().ready:
                return provider
        raise RuntimeError("No production AI engine is ready. Configure ACE-Step or DiffRhythm. Drellion will not silently fall back to the Basic Test Engine.")

    def generate(self, request: GenerationRequest, preferred: str | None = None, progress: Callable[[str], None] | None = None) -> GenerationResult:
        return self.ready_provider(preferred).generate(request, progress)


def create_broker(preferences: dict[str, Any]) -> EngineBroker:
    providers: list[GenerationProvider] = []
    ace_url = str(preferences.get("ace_step_url") or "").strip()
    diff_url = str(preferences.get("diffrhythm_url") or "").strip()
    diff_local = str(preferences.get("diffrhythm_local") or "").strip()
    if ace_url: providers.append(AceStepHttpProvider(ace_url))
    if diff_url: providers.append(DiffRhythmHttpProvider(diff_url))
    if diff_local: providers.append(DiffRhythmLocalProvider(diff_local))
    return EngineBroker(providers, explicit_basic=bool(preferences.get("explicit_basic_test_engine")))
