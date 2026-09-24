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
