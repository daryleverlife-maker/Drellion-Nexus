from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class ProviderState(str, Enum):
    READY = 'Ready'
    NEEDS_SETUP = 'Needs setup'
    OFFLINE = 'Offline'
    DISABLED = 'Disabled'
    ERROR = 'Error'


@dataclass(frozen=True)
class ProviderCapabilities:
    vocal_conditioning: bool = False
    reference_audio: bool = False
    lyrics: bool = False
    complete_song: bool = False
    repaint: bool = False
    stems: bool = False
    remote: bool = False


@dataclass
class ProviderStatus:
    id: str
    name: str
    state: ProviderState
    detail: str = ''
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)


class GenerationProvider:
    id = 'base'
    name = 'Generation Provider'
    capabilities = ProviderCapabilities()

    def status(self, settings: dict[str, Any]) -> ProviderStatus:
        return ProviderStatus(self.id, self.name, ProviderState.NEEDS_SETUP, 'Not configured.', self.capabilities)

    def generate(self, **kwargs):
        raise NotImplementedError


class RemoteHttpProvider(GenerationProvider):
    default_url = ''

    def endpoint(self, settings: dict[str, Any]) -> str:
        return str(settings.get(f'provider_{self.id}_url', self.default_url) or '').strip().rstrip('/')

    def status(self, settings: dict[str, Any]) -> ProviderStatus:
        url = self.endpoint(settings)
        if not url:
            return ProviderStatus(self.id, self.name, ProviderState.NEEDS_SETUP, 'Set an endpoint URL.', self.capabilities)
        health_paths = ('/health', '/docs', '/')
        for suffix in health_paths:
            try:
                req = urllib.request.Request(url + suffix, headers={'User-Agent': 'Drellion-Nexus/2'})
                with urllib.request.urlopen(req, timeout=2.5) as response:
                    if 200 <= response.status < 500:
                        return ProviderStatus(self.id, self.name, ProviderState.READY, url, self.capabilities)
            except Exception:
                continue
        return ProviderStatus(self.id, self.name, ProviderState.OFFLINE, f'Endpoint unavailable: {url}', self.capabilities)

    @staticmethod
    def post_json(url: str, payload: dict[str, Any], timeout: float = 600.0) -> dict[str, Any]:
        body = json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(
            url,
            data=body,
            method='POST',
            headers={'Content-Type': 'application/json', 'User-Agent': 'Drellion-Nexus/2'},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')[-4000:]
            raise RuntimeError(f'Provider HTTP {exc.code}: {detail}') from exc


class AceStepProvider(RemoteHttpProvider):
    id = 'ace_step'
    name = 'ACE-Step 1.5'
    capabilities = ProviderCapabilities(
        vocal_conditioning=True,
        reference_audio=True,
        lyrics=True,
        complete_song=True,
        repaint=True,
        stems=True,
        remote=True,
    )

    @staticmethod
    def _multipart(fields: dict[str, str], files: dict[str, Path]) -> tuple[bytes, str]:
        boundary = '----DrellionNexus' + uuid.uuid4().hex
        body = bytearray()
        for name, value in fields.items():
            body.extend(f'--{boundary}\r\n'.encode())
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            body.extend(str(value).encode('utf-8'))
            body.extend(b'\r\n')
        for name, path in files.items():
            mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            body.extend(f'--{boundary}\r\n'.encode())
            body.extend(
                f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'.encode()
            )
            body.extend(f'Content-Type: {mime}\r\n\r\n'.encode())
            body.extend(path.read_bytes())
            body.extend(b'\r\n')
        body.extend(f'--{boundary}--\r\n'.encode())
        return bytes(body), f'multipart/form-data; boundary={boundary}'

    def _headers(self, settings: dict[str, Any], content_type: str | None = None) -> dict[str, str]:
        headers = {'User-Agent': 'Drellion-Nexus/2'}
        token = str(os.environ.get('DRELLION_ACE_TOKEN', '') or settings.get('provider_ace_step_token', '') or '').strip()
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if content_type:
            headers['Content-Type'] = content_type
        return headers

    def _download_audio_refs(
        self,
        settings: dict[str, Any],
        endpoint: str,
        refs: list[str],
        output_dir: str | Path,
        batch_size: int,
    ) -> list[Path]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []
        for index, file_ref in enumerate(refs[:batch_size], start=1):
            if not file_ref:
                continue
            url = file_ref if file_ref.startswith('http') else endpoint + file_ref
            req = urllib.request.Request(url, headers=self._headers(settings))
            with urllib.request.urlopen(req, timeout=180.0) as response:
                data = response.read()
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query)
            path_hint = query.get('path', [''])[0]
            suffix = Path(path_hint or parsed.path).suffix or '.flac'
            target = out / f'ace-preview-{index}{suffix}'
            target.write_bytes(data)
            downloaded.append(target)
        return downloaded

    @staticmethod
    def _modern_result_refs(payload: dict[str, Any]) -> list[str]:
        refs: list[str] = []
        for key in ('audio_paths', 'files', 'outputs'):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        refs.append(item)
                    elif isinstance(item, dict):
                        ref = item.get('file') or item.get('url') or item.get('path')
                        if ref:
                            refs.append(str(ref))
        for key in ('first_audio_path', 'second_audio_path', 'audio_path'):
            value = payload.get(key)
            if value:
                refs.append(str(value))
        result = payload.get('result')
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = None
        if isinstance(result, list):
            for item in result:
                if isinstance(item, str):
                    refs.append(item)
                elif isinstance(item, dict):
                    ref = item.get('file') or item.get('url') or item.get('path')
                    if ref:
                        refs.append(str(ref))
        elif isinstance(result, dict):
            refs.extend(AceStepProvider._modern_result_refs(result))
        seen = set()
        return [x for x in refs if x and not (x in seen or seen.add(x))]

    def _generate_modern(
        self,
        settings: dict[str, Any],
        endpoint: str,
        fields: dict[str, str],
        files: dict[str, Path],
        output_dir: str | Path,
        batch_size: int,
        timeout: float,
    ) -> list[Path]:
        body, content_type = self._multipart(fields, files)
        request = urllib.request.Request(
            endpoint + '/v1/music/generate',
            data=body,
            method='POST',
            headers=self._headers(settings, content_type),
        )
        with urllib.request.urlopen(request, timeout=120.0) as response:
            created = json.loads(response.read().decode('utf-8'))
        job_id = created.get('job_id') or (created.get('data') or {}).get('job_id')
        if not job_id:
            raise RuntimeError(f'ACE-Step modern API did not return a job_id: {created}')

        started = time.monotonic()
        while time.monotonic() - started < timeout:
            request = urllib.request.Request(
                endpoint + '/v1/jobs/' + urllib.parse.quote(str(job_id), safe=''),
                headers=self._headers(settings),
            )
            with urllib.request.urlopen(request, timeout=30.0) as response:
                payload = json.loads(response.read().decode('utf-8'))
            data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
            status = str(data.get('status', '') or '').lower()
            if status == 'failed':
                raise RuntimeError(data.get('error') or 'ACE-Step generation failed.')
            if status == 'succeeded':
                refs = self._modern_result_refs(data)
                downloaded = self._download_audio_refs(settings, endpoint, refs, output_dir, batch_size)
                if downloaded:
                    return downloaded
                raise RuntimeError(f'ACE-Step succeeded but returned no audio URLs: {data}')
            time.sleep(2.0)
        raise TimeoutError('ACE-Step modern API generation timed out.')

    def _generate_legacy(
        self,
        settings: dict[str, Any],
        endpoint: str,
        fields: dict[str, str],
        files: dict[str, Path],
        output_dir: str | Path,
        batch_size: int,
        timeout: float,
    ) -> list[Path]:
        body, content_type = self._multipart(fields, files)
        request = urllib.request.Request(
            endpoint + '/release_task',
            data=body,
            method='POST',
            headers=self._headers(settings, content_type),
        )
        with urllib.request.urlopen(request, timeout=120.0) as response:
            created = json.loads(response.read().decode('utf-8'))
        task_id = (created.get('data') or {}).get('task_id')
        if not task_id:
            raise RuntimeError(f'ACE-Step legacy API did not return a task id: {created}')

        started = time.monotonic()
        while time.monotonic() - started < timeout:
            payload = json.dumps({'task_id_list': [task_id]}).encode('utf-8')
            query = urllib.request.Request(
                endpoint + '/query_result',
                data=payload,
                method='POST',
                headers=self._headers(settings, 'application/json'),
            )
            with urllib.request.urlopen(query, timeout=30.0) as response:
                status_payload = json.loads(response.read().decode('utf-8'))
            entries = status_payload.get('data') or []
            entry = entries[0] if entries else {}
            status = int(entry.get('status', 0) or 0)
            if status == 2:
                raise RuntimeError(entry.get('error') or 'ACE-Step generation failed.')
            if status == 1:
                raw_result = entry.get('result', '[]')
                result = json.loads(raw_result) if isinstance(raw_result, str) else (raw_result or [])
                refs = []
                for item in result:
                    if isinstance(item, str):
                        refs.append(item)
                    elif isinstance(item, dict) and item.get('file'):
                        refs.append(str(item['file']))
                downloaded = self._download_audio_refs(settings, endpoint, refs, output_dir, batch_size)
                if downloaded:
                    return downloaded
                raise RuntimeError('ACE-Step legacy API completed but returned no downloadable audio.')
            time.sleep(2.0)
        raise TimeoutError('ACE-Step legacy API generation timed out.')

    def generate_complete(
        self,
        settings: dict[str, Any],
        *,
        source_audio: str | Path,
        reference_audio: str | Path | None,
        lyrics: str,
        prompt: str,
        output_dir: str | Path,
        duration: float,
        batch_size: int = 3,
        bpm: float | None = None,
        cover_strength: float = 0.25,
        timeout: float = 1200.0,
    ) -> list[Path]:
        endpoint = self.endpoint(settings)
        if not endpoint:
            raise RuntimeError('ACE-Step endpoint is not configured.')

        source = Path(source_audio)
        if not source.is_file():
            raise FileNotFoundError(source)
        files = {'src_audio': source}
        if reference_audio:
            ref = Path(reference_audio)
            if ref.is_file():
                files['reference_audio'] = ref

        fields = {
            'task_type': 'complete',
            # Both names are accepted by different ACE-Step HTTP generations.
            'prompt': prompt,
            'caption': prompt,
            'lyrics': lyrics or '',
            'audio_duration': f'{max(4.0, float(duration)):.3f}',
            'batch_size': str(max(1, min(8, int(batch_size)))),
            'thinking': 'true',
            'use_format': 'true',
            'audio_cover_strength': f'{max(0.0, min(1.0, float(cover_strength))):.3f}',
            'audio_format': 'flac',
        }
        if bpm and bpm > 0:
            fields['bpm'] = str(round(float(bpm)))

        preference = str(settings.get('provider_ace_step_api', 'auto') or 'auto').lower()
        errors: list[str] = []
        order = ('modern', 'legacy') if preference == 'auto' else (preference,)
        for mode in order:
            try:
                if mode == 'modern':
                    return self._generate_modern(
                        settings, endpoint, fields, files, output_dir, batch_size, timeout
                    )
                if mode == 'legacy':
                    return self._generate_legacy(
                        settings, endpoint, fields, files, output_dir, batch_size, timeout
                    )
                raise ValueError(f'Unknown ACE-Step API mode: {mode}')
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode('utf-8', errors='replace')[-1200:]
                errors.append(f'{mode}: HTTP {exc.code} {detail}')
                if preference != 'auto' or exc.code not in {404, 405, 422}:
                    break
            except (RuntimeError, ValueError) as exc:
                errors.append(f'{mode}: {exc}')
                if preference != 'auto':
                    break

        raise RuntimeError(
            'ACE-Step endpoint could not generate with a supported API variant. '
            + ' | '.join(errors)
        )


class DiffRhythmProvider(RemoteHttpProvider):
    id = 'diff_rhythm'
    name = 'DiffRhythm 2'
    capabilities = ProviderCapabilities(
        vocal_conditioning=False,
        reference_audio=True,
        lyrics=True,
        complete_song=True,
        repaint=False,
        stems=False,
        remote=True,
    )


class YueProvider(RemoteHttpProvider):
    id = 'yue'
    name = 'YuE'
    capabilities = ProviderCapabilities(
        vocal_conditioning=False,
        reference_audio=True,
        lyrics=True,
        complete_song=True,
        repaint=False,
        stems=False,
        remote=True,
    )


class BasicTestProvider(GenerationProvider):
    id = 'basic_test'
    name = 'Drellion Basic Test Engine'
    capabilities = ProviderCapabilities(vocal_conditioning=True, reference_audio=True, lyrics=True, complete_song=True)

    def status(self, settings: dict[str, Any]) -> ProviderStatus:
        enabled = bool(settings.get('enable_basic_test_engine', False))
        return ProviderStatus(
            self.id,
            self.name,
            ProviderState.READY if enabled else ProviderState.DISABLED,
            'Developer/testing quality only.' if enabled else 'Disabled by default; never used as silent fallback.',
            self.capabilities,
        )


class ProviderBroker:
    """Provider registry and explicit routing.

    v2 never silently falls back from a failed music model to the Basic Test
    Engine. Auto mode selects only providers reporting READY.
    """

    def __init__(self):
        self.providers: dict[str, GenerationProvider] = {
            provider.id: provider
            for provider in (AceStepProvider(), DiffRhythmProvider(), YueProvider(), BasicTestProvider())
        }

    def statuses(self, settings: dict[str, Any]) -> list[ProviderStatus]:
        return [provider.status(settings) for provider in self.providers.values()]

    def get(self, provider_id: str) -> GenerationProvider:
        try:
            return self.providers[provider_id]
        except KeyError as exc:
            raise ValueError(f'Unknown generation provider: {provider_id}') from exc

    def choose(self, settings: dict[str, Any], *, require_vocal: bool = True) -> GenerationProvider:
        requested = str(settings.get('generation_provider', 'auto') or 'auto')
        if requested != 'auto':
            provider = self.get(requested)
            status = provider.status(settings)
            if status.state != ProviderState.READY:
                raise RuntimeError(f'{provider.name} is not ready: {status.detail}')
            if require_vocal and not provider.capabilities.vocal_conditioning:
                raise RuntimeError(f'{provider.name} does not support vocal-conditioned Complete generation.')
            return provider

        preferred = ('ace_step', 'diff_rhythm', 'yue')
        for provider_id in preferred:
            provider = self.providers[provider_id]
            status = provider.status(settings)
            if status.state != ProviderState.READY:
                continue
            if require_vocal and not provider.capabilities.vocal_conditioning:
                continue
            return provider

        raise RuntimeError(
            'No production-quality generation engine is ready. Configure ACE-Step, '
            'DiffRhythm or another provider. Drellion Basic will not be used silently.'
        )
