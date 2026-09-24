from pathlib import Path
import pytest

from drellion.accessibility import AccessibilitySettings
from drellion.project import ProjectState, MediaSlot
from drellion.providers import EngineBroker, ProviderState, ProviderStatus


def test_v2_project_layout_and_roundtrip(tmp_path: Path):
    project = ProjectState(name="V2 Test", artist="Tester")
    project.add_source("vocal.wav", role="Lead Vocal")
    project.sources[0].preserve = True
    project.add_reference(path="ref1.wav", title="Reference One")
    project.references[0].influences["bass"] = 0.0
    folders = project.ensure_layout(tmp_path / "project")
    assert folders["exports"].is_dir()
    path = project.save(tmp_path / "project.drellion")
    loaded = ProjectState.load(path)
    assert loaded.schema_version == 3
    assert loaded.sources[0].role == "Lead Vocal"
    assert loaded.sources[0].preserve is True
    assert loaded.references[0].influences["bass"] == 0.0


def test_v1_fields_migrate_to_sources_and_references():
    project = ProjectState(vocal=MediaSlot("voice.wav", "Voice"), reference=MediaSlot("ref.wav", "Ref"))
    loaded = ProjectState.from_dict(project.to_dict() | {"sources": [], "references": []})
    assert loaded.sources[0].path == "voice.wav"
    assert loaded.sources[0].role == "Lead Vocal"
    assert loaded.references[0].path == "ref.wav"


def test_auto_mode_reference_limit():
    project = ProjectState(mode="auto")
    for i in range(6):
        project.add_reference(title=f"Ref {i}")
    with pytest.raises(ValueError):
        project.add_reference(title="Ref 7")


def test_accessibility_normalizes_scaling():
    settings = AccessibilitySettings(ui_scale=900, text_scale=2)
    settings.normalized()
    assert settings.ui_scale == 200
    assert settings.text_scale == 100


class FakeProvider:
    id = "fake"
    name = "Fake"
    def __init__(self, state):
        self.state = state
    def status(self):
        return ProviderStatus(self.id, self.name, self.state)


def test_engine_broker_never_silently_uses_unready_provider():
    broker = EngineBroker()
    broker.register(FakeProvider(ProviderState.MISSING))
    with pytest.raises(RuntimeError):
        broker.choose("auto")


def test_engine_broker_uses_ready_provider():
    broker = EngineBroker()
    missing = FakeProvider(ProviderState.MISSING)
    missing.id = "missing"
    ready = FakeProvider(ProviderState.READY)
    ready.id = "ready"
    broker.register(missing)
    broker.register(ready)
    assert broker.choose("auto").id == "ready"
