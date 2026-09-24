from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDial, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)


class Knob(QWidget):
    def __init__(self, title: str, minimum: int, maximum: int, value: int, suffix: str = "%", parent=None):
        super().__init__(parent)
        self.suffix = suffix
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignCenter)
        self.dial = QDial()
        self.dial.setRange(minimum, maximum)
        self.dial.setValue(value)
        self.dial.setNotchesVisible(True)
        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.dial, 0, Qt.AlignCenter)
        layout.addWidget(self.value_label)
        self.dial.valueChanged.connect(self._refresh)
        self._refresh(value)

    def _refresh(self, value: int):
        self.value_label.setText(f"{value}{self.suffix}")

    def value(self) -> int:
        return self.dial.value()

    def setValue(self, value: int):
        self.dial.setValue(value)


class AdvancedControlsDialog(QDialog):
    """Producer controls stored as non-destructive project settings."""

    DEFAULTS = {
        "reference_strength": 85,
        "groove_strength": 80,
        "energy_strength": 85,
        "tone_strength": 75,
        "stereo_strength": 65,
        "dynamics_strength": 70,
        "vocal_timing": 45,
        "vocal_tuning": 35,
        "vocal_presence": 55,
        "vocal_space": 35,
        "drum_density": 55,
        "bass_weight": 55,
        "harmony_density": 50,
        "transition_amount": 45,
        "master_reference_strength": 70,
        "master_punch": 50,
        "master_width": 50,
    }

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Drellion Nexus — Advanced Controls")
        self.resize(860, 620)
        self._knobs: dict[str, Knob] = {}

        outer = QVBoxLayout(self)
        title = QLabel("CUSTOM CONTROL")
        title.setStyleSheet("font-size:18pt;font-weight:700;")
        outer.addWidget(title)
        note = QLabel(
            "These controls are non-destructive. AI Suggest can restore a strong "
            "reference-guided starting point, while Reset restores neutral defaults."
        )
        note.setWordWrap(True)
        note.setObjectName("Muted")
        outer.addWidget(note)

        tabs = QTabWidget()
        tabs.addTab(self._reference_tab(), "Reference")
        tabs.addTab(self._vocal_tab(), "Vocal")
        tabs.addTab(self._arrangement_tab(), "Arrangement")
        tabs.addTab(self._master_tab(), "Master")
        outer.addWidget(tabs, 1)

        row = QHBoxLayout()
        suggest = QPushButton("AI Suggest")
        suggest.clicked.connect(self.ai_suggest)
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset_defaults)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        apply = QPushButton("Apply")
        apply.setObjectName("Primary")
        apply.clicked.connect(self.apply)
        row.addWidget(suggest)
        row.addWidget(reset)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(apply)
        outer.addLayout(row)

        self.load_project()

    def _knob_grid(self, specs):
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        for key, title in specs:
            value = int(self.project.settings.get(key, self.DEFAULTS[key]))
            knob = Knob(title, 0, 100, value)
            self._knobs[key] = knob
            row.addWidget(knob)
        row.addStretch(1)
        return widget

    def _reference_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._knob_grid([
            ("reference_strength", "Overall"),
            ("groove_strength", "Groove"),
            ("energy_strength", "Energy"),
        ]))
        layout.addWidget(self._knob_grid([
            ("tone_strength", "Tone"),
            ("stereo_strength", "Stereo"),
            ("dynamics_strength", "Dynamics"),
        ]))
        layout.addStretch(1)
        return widget

    def _vocal_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._knob_grid([
            ("vocal_timing", "Timing"),
            ("vocal_tuning", "Pitch"),
            ("vocal_presence", "Presence"),
            ("vocal_space", "Space"),
        ]))
        layout.addStretch(1)
        return widget

    def _arrangement_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._knob_grid([
            ("drum_density", "Drums"),
            ("bass_weight", "Bass"),
            ("harmony_density", "Harmony"),
            ("transition_amount", "Transitions"),
        ]))
        layout.addStretch(1)
        return widget

    def _master_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._knob_grid([
            ("master_reference_strength", "Ref Match"),
            ("master_punch", "Punch"),
            ("master_width", "Width"),
        ]))
        layout.addStretch(1)
        return widget

    def load_project(self):
        for key, knob in self._knobs.items():
            knob.setValue(int(self.project.settings.get(key, self.DEFAULTS[key])))

    def ai_suggest(self):
        values = {
            **self.DEFAULTS,
            "reference_strength": 90,
            "groove_strength": 85,
            "energy_strength": 90,
            "tone_strength": 78,
            "stereo_strength": 70,
            "dynamics_strength": 76,
            "vocal_timing": 52,
            "vocal_tuning": 40,
            "drum_density": 62,
            "transition_amount": 58,
            "master_reference_strength": 76,
        }
        for key, value in values.items():
            if key in self._knobs:
                self._knobs[key].setValue(value)

    def reset_defaults(self):
        for key, knob in self._knobs.items():
            knob.setValue(self.DEFAULTS[key])

    def apply(self):
        for key, knob in self._knobs.items():
            self.project.settings[key] = knob.value()
        self.project.touch()
        self.accept()
