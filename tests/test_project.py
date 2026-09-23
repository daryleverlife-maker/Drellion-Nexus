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
