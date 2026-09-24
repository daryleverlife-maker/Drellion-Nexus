from drellion.project import ProjectState
from drellion.audio.contracts import ReferenceAnalysis
from drellion.engine import NexusEngine
from drellion.ui.advanced import AdvancedControlsDialog


def test_advanced_defaults_are_bounded():
    for value in AdvancedControlsDialog.DEFAULTS.values():
        assert 0 <= value <= 100


def test_custom_reference_guidance_overrides_preset():
    state = ProjectState()
    state.reference_influence = "Light"
    state.originality_protection = "Maximum"
    state.settings["reference_strength"] = 90
    state.settings["groove_strength"] = 100
    state.settings["energy_strength"] = 0

    reference = ReferenceAnalysis(
        bpm=120.0,
        duration=180.0,
        energy_curve=[1.0] * 12,
    )

    bpm, energy = NexusEngine._reference_guidance(state, reference, variant=0)

    # Maximum custom groove control should pull strongly toward reference BPM
    # even when the simple preset says Light.
    assert 118.0 <= bpm <= 122.0

    # Zero custom energy influence should fall back to the neutral energy bed.
    assert all(abs(value - 0.72) < 1e-6 for value in energy)


def test_custom_controls_roundtrip_in_project(tmp_path):
    state = ProjectState()
    state.settings.update({
        "reference_strength": 91,
        "groove_strength": 84,
        "master_punch": 67,
        "master_width": 43,
    })
    path = state.save(tmp_path / "advanced.drellion")
    loaded = ProjectState.load(path)
    assert loaded.settings["reference_strength"] == 91
    assert loaded.settings["groove_strength"] == 84
    assert loaded.settings["master_punch"] == 67
    assert loaded.settings["master_width"] == 43
