from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from ..preferences import load_preferences, save_preferences
from .accessibility import AccessibilityDialog


class SettingsDialog(QDialog):
    PROVIDERS = {
        "Automatic": "auto",
        "ACE-Step 1.5": "ace_step",
        "DiffRhythm 2": "diff_rhythm",
        "YuE": "yue",
    }

    def __init__(self, main, parent=None):
        super().__init__(parent or main)
        self.main = main
        self.values = load_preferences()
        self.setWindowTitle("Drellion Nexus — Settings")
        self.resize(720, 650)

        outer = QVBoxLayout(self)
        title = QLabel("SETTINGS")
        title.setStyleSheet("font-size:18pt;font-weight:700;")
        outer.addWidget(title)
        tabs = QTabWidget()
        tabs.addTab(self._storage_tab(), "Storage")
        tabs.addTab(self._engine_tab(), "AI Engines")
        tabs.addTab(self._behavior_tab(), "Behavior")
        tabs.addTab(self._accessibility_tab(), "Accessibility")
        outer.addWidget(tabs, 1)

        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save Settings")
        save.setObjectName("Primary")
        save.clicked.connect(self.save)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(save)
        outer.addLayout(row)

    def _folder_row(self, key):
        wrapper = QWidget()
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        field = QLineEdit(str(self.values.get(key, "") or ""))
        button = QPushButton("Browse…")
        button.clicked.connect(lambda: self._browse(field))
        row.addWidget(field, 1)
        row.addWidget(button)
        return wrapper, field

    def _browse(self, field):
        path = QFileDialog.getExistingDirectory(self, "Choose Folder", field.text().strip())
        if path:
            field.setText(path)

    def _storage_tab(self):
        widget = QWidget()
        form = QFormLayout(widget)
        wrapper, self.project_root = self._folder_row("project_root")
        form.addRow("Projects", wrapper)
        wrapper, self.export_root = self._folder_row("export_root")
        form.addRow("Exports", wrapper)
        wrapper, self.sound_root = self._folder_row("sound_library_root")
        form.addRow("Sound library", wrapper)
        wrapper, self.model_root = self._folder_row("model_root")
        form.addRow("AI models", wrapper)
        wrapper, self.cache_root = self._folder_row("cache_root")
        form.addRow("Cache", wrapper)
        return widget

    def _engine_tab(self):
        widget = QWidget()
        form = QFormLayout(widget)
        self.provider = QComboBox()
        self.provider.addItems(self.PROVIDERS.keys())
        wanted = str(self.values.get("generation_provider", "auto"))
        for label, value in self.PROVIDERS.items():
            if value == wanted:
                self.provider.setCurrentText(label)
                break
        form.addRow("Default engine", self.provider)
        self.ace = QLineEdit(str(self.values.get("provider_ace_step_url", "") or ""))
        self.diff = QLineEdit(str(self.values.get("provider_diff_rhythm_url", "") or ""))
        self.yue = QLineEdit(str(self.values.get("provider_yue_url", "") or ""))
        form.addRow("ACE-Step endpoint", self.ace)
        form.addRow("DiffRhythm endpoint", self.diff)
        form.addRow("YuE endpoint", self.yue)
        note = QLabel("API tokens are not stored in project files. Authenticated servers should use environment/OS credential mechanisms.")
        note.setWordWrap(True)
        note.setObjectName("Muted")
        form.addRow(note)
        return widget

    def _behavior_tab(self):
        widget = QWidget()
        form = QFormLayout(widget)
        self.autosave = QCheckBox("Enable autosave and recovery")
        self.autosave.setChecked(bool(self.values.get("autosave_enabled", True)))
        form.addRow(self.autosave)
        self.interval = QSpinBox()
        self.interval.setRange(30, 1800)
        self.interval.setSuffix(" seconds")
        self.interval.setValue(int(self.values.get("autosave_seconds", 120)))
        form.addRow("Autosave interval", self.interval)
        self.consolidate = QCheckBox("Copy imported media into project folders")
        self.consolidate.setChecked(bool(self.values.get("consolidate_imports", True)))
        form.addRow(self.consolidate)
        return widget

    def _accessibility_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        note = QLabel("Accessibility preferences include UI/text scaling, themes, font preference, large controls, focus visibility and screen-reader feedback.")
        note.setWordWrap(True)
        layout.addWidget(note)
        button = QPushButton("Open Accessibility Center")
        button.clicked.connect(lambda: AccessibilityDialog(self.main.project, self).exec())
        layout.addWidget(button)
        layout.addStretch(1)
        return widget

    def save(self):
        self.values.update({
            "project_root": self.project_root.text().strip(),
            "export_root": self.export_root.text().strip(),
            "sound_library_root": self.sound_root.text().strip(),
            "model_root": self.model_root.text().strip(),
            "cache_root": self.cache_root.text().strip(),
            "generation_provider": self.PROVIDERS[self.provider.currentText()],
            "provider_ace_step_url": self.ace.text().strip(),
            "provider_diff_rhythm_url": self.diff.text().strip(),
            "provider_yue_url": self.yue.text().strip(),
            "autosave_enabled": self.autosave.isChecked(),
            "autosave_seconds": self.interval.value(),
            "consolidate_imports": self.consolidate.isChecked(),
            "accessibility": dict(self.main.project.settings.get("accessibility", {}) or {}),
        })
        save_preferences(self.values)

        p = self.main.project
        p.storage.project_root = self.values["project_root"]
        p.storage.export_root = self.values["export_root"]
        p.storage.sound_library_root = self.values["sound_library_root"]
        p.storage.model_root = self.values["model_root"]
        p.storage.cache_root = self.values["cache_root"]
        if self.values["sound_library_root"]:
            p.sound_library_path = self.values["sound_library_root"]
        for key in (
            "generation_provider", "provider_ace_step_url", "provider_diff_rhythm_url",
            "provider_yue_url", "autosave_enabled", "consolidate_imports",
        ):
            p.settings[key] = self.values[key]
        self.main.autosave_timer.setInterval(self.values["autosave_seconds"] * 1000)
        self.main.snapshot("Changed application settings")
        self.accept()
