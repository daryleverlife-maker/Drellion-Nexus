from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
import json
import urllib.error
import urllib.request


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
    capabilities = ProviderCapabilities(complete_song=True)

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
