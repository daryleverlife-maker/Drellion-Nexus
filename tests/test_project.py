from drellion.history import History
from drellion.project import ProjectState


def test_project_round_trip(tmp_path):
    state=ProjectState(name="Rise")
    state.vocal.path="vocal.wav"
    state.reference.path="reference.flac"
    path=state.save(tmp_path/"test")
    loaded=ProjectState.load(path)
    assert loaded.name=="Rise"
    assert loaded.vocal.path=="vocal.wav"
    assert loaded.reference.path=="reference.flac"


def test_history_undo_redo():
    state=ProjectState(name="A")
    history=History(state)
    state.name="B"
    history.push("rename",state)
    previous=history.undo()
    assert previous.name=="A"
    restored=history.redo()
    assert restored.name=="B"


def test_v2_multi_source_reference_round_trip(tmp_path):
    state = ProjectState(name="V2")
    vocal = state.add_source("lead.wav", role="Lead Vocal", preserve=True)
    state.add_source("guitar.wav", role="Instrument", preserve=True)
    reference = state.add_reference(path="ref.wav", title="Reference A", influence=0.65)
    state.add_reference(youtube_url="https://www.youtube.com/watch?v=test", title="Reference B", influence=0.35)
    state.active_vocal_source_id = vocal.id
    state.active_reference_id = reference.id
    state.storage.project_root = str(tmp_path / "Projects")
    path = state.save(tmp_path / "v2.drellion")

    loaded = ProjectState.load(path)
    assert loaded.schema_version >= 3
    assert len(loaded.sources) >= 2
    assert len(loaded.references) >= 2
    assert loaded.vocal.path == "lead.wav"
    assert loaded.reference.path == "ref.wav"
    assert loaded.storage.project_root.endswith("Projects")
