import pytest

from drellion.project import ProjectState
from drellion.providers import ProviderBroker, ProviderState


def test_basic_engine_is_disabled_by_default():
    broker = ProviderBroker()
    state = ProjectState()
    status = broker.get("basic_test").status(state.settings)
    assert status.state == ProviderState.DISABLED


def test_auto_never_silently_selects_basic_engine():
    broker = ProviderBroker()
    state = ProjectState()
    state.settings["provider_ace_step_url"] = ""
    state.settings["provider_diff_rhythm_url"] = ""
    state.settings["provider_yue_url"] = ""
    state.settings["enable_basic_test_engine"] = True
    with pytest.raises(RuntimeError, match="No production-quality generation engine"):
        broker.choose(state.settings, require_vocal=True)


def test_explicit_basic_engine_can_be_enabled():
    broker = ProviderBroker()
    state = ProjectState()
    state.settings["generation_provider"] = "basic_test"
    state.settings["enable_basic_test_engine"] = True
    provider = broker.choose(state.settings, require_vocal=False)
    assert provider.id == "basic_test"


def test_ace_modern_result_refs_accepts_current_job_shapes():
    from drellion.providers import AceStepProvider
    payload = {
        "status": "succeeded",
        "audio_paths": ["/v1/audio?path=%2Ftmp%2Fa.flac"],
        "first_audio_path": "/v1/audio?path=%2Ftmp%2Fa.flac",
        "second_audio_path": "/v1/audio?path=%2Ftmp%2Fb.flac",
        "result": [{"file": "/v1/audio?path=%2Ftmp%2Fc.flac"}],
    }
    refs = AceStepProvider._modern_result_refs(payload)
    assert len(refs) == 3
    assert refs[0].endswith("a.flac")
    assert any("b.flac" in item for item in refs)
    assert any("c.flac" in item for item in refs)


def test_ace_modern_result_refs_accepts_nested_result():
    from drellion.providers import AceStepProvider
    refs = AceStepProvider._modern_result_refs({
        "result": {"audio_paths": ["https://example.test/a.wav"]}
    })
    assert refs == ["https://example.test/a.wav"]
