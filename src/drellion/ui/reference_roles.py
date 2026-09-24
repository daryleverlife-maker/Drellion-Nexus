from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


ROLE_LABELS = {
    "drums": "Drum character",
    "bass": "Bass / low-end character",
    "energy": "Energy curve",
    "arrangement": "Arrangement shape",
    "harmony": "Harmony direction",
    "tone": "Tonal balance",
    "stereo": "Stereo character",
    "master": "Mastering character",
}


class ReferenceRolesDialog(QDialog):
    def __init__(self, reference, parent=None):
        super().__init__(parent)
        self.reference = reference
        self.setWindowTitle("Reference Influence Matrix")
        self.resize(520, 520)
        outer = QVBoxLayout(self)
        title = QLabel(reference.title or "Reference")
        title.setStyleSheet("font-size:16pt;font-weight:700;")
        outer.addWidget(title)
        note = QLabel(
            "Set which production characteristics this reference should influence. "
            "These values guide descriptors and model conditioning; they do not copy source audio."
        )
        note.setWordWrap(True)
        note.setObjectName("Muted")
        outer.addWidget(note)
        form = QFormLayout()
        self.controls = {}
        for key, label in ROLE_LABELS.items():
            control = QDoubleSpinBox()
            control.setRange(0, 100)
            control.setDecimals(0)
            control.setSuffix("%")
            control.setValue(float(reference.roles.get(key, 0.0)) * 100.0)
            self.controls[key] = control
            form.addRow(label, control)
        outer.addLayout(form)
        outer.addStretch(1)
        row = QHBoxLayout()
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        apply = QPushButton("Apply")
        apply.setObjectName("Primary")
        apply.clicked.connect(self.apply)
        row.addWidget(reset)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(apply)
        outer.addLayout(row)

    def reset(self):
        defaults = {
            "drums": 100, "bass": 100, "energy": 100, "arrangement": 100,
            "harmony": 50, "tone": 100, "stereo": 100, "master": 100,
        }
        for key, value in defaults.items():
            self.controls[key].setValue(value)

    def apply(self):
        self.reference.roles = {
            key: control.value() / 100.0
            for key, control in self.controls.items()
        }
        self.accept()
