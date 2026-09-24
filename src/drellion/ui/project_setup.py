from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout,
)

from ..project import ProjectState
from ..storage import ensure_project_folders


class ProjectSetupDialog(QDialog):
    def __init__(self, state: ProjectState | None = None, parent=None):
        super().__init__(parent)
        self.state = state or ProjectState()
        self.setWindowTitle('New Drellion Nexus Project')
        self.resize(680, 500)

        outer = QVBoxLayout(self)
        title = QLabel('NEW PROJECT')
        title.setStyleSheet('font-size:18pt;font-weight:700;')
        outer.addWidget(title)

        form = QFormLayout()
        self.name = QLineEdit(self.state.name if self.state.name != 'Untitled' else '')
        self.name.setPlaceholderText('Song / project name')
        self.artist = QLineEdit(self.state.artist)
        self.artist.setPlaceholderText('Artist name (optional)')
        form.addRow('Project name', self.name)
        form.addRow('Artist', self.artist)

        self.project_root = QLineEdit(self.state.storage.project_root or str(Path.home() / 'Drellion Nexus' / 'Projects'))
        self.export_root = QLineEdit(self.state.storage.export_root)
        self.sound_root = QLineEdit(self.state.storage.sound_library_root or self.state.sound_library_path)
        self.model_root = QLineEdit(self.state.storage.model_root or str(Path.home() / 'Drellion Nexus' / 'Models'))
        self.cache_root = QLineEdit(self.state.storage.cache_root or str(Path.home() / 'Drellion Nexus' / 'Cache'))

        form.addRow('Projects folder', self._path_row(self.project_root))
        form.addRow('Default export folder', self._path_row(self.export_root))
        form.addRow('Sound library', self._path_row(self.sound_root))
        form.addRow('AI models', self._path_row(self.model_root))
        form.addRow('Cache', self._path_row(self.cache_root))
        outer.addLayout(form)

        self.consolidate = QCheckBox('Copy imported media into the project Sources/References folders')
        self.consolidate.setChecked(True)
        outer.addWidget(self.consolidate)
        self.recovery = QCheckBox('Enable autosave and crash recovery')
        self.recovery.setChecked(True)
        outer.addWidget(self.recovery)
        outer.addStretch(1)

        row = QHBoxLayout()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        create = QPushButton('Create Project')
        create.setObjectName('Primary')
        create.clicked.connect(self.accept_project)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(create)
        outer.addLayout(row)

    def _path_row(self, field):
        wrapper = QDialog()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        browse = QPushButton('Browse…')
        browse.clicked.connect(lambda: self.choose_folder(field))
        layout.addWidget(field, 1)
        layout.addWidget(browse)
        return wrapper

    def choose_folder(self, field):
        path = QFileDialog.getExistingDirectory(self, 'Choose Folder', field.text().strip())
        if path:
            field.setText(path)

    def accept_project(self):
        name = self.name.text().strip()
        if not name:
            self.name.setFocus()
            return
        self.state.name = name
        self.state.artist = self.artist.text().strip()
        self.state.storage.project_root = self.project_root.text().strip()
        self.state.storage.export_root = self.export_root.text().strip()
        self.state.storage.sound_library_root = self.sound_root.text().strip()
        self.state.storage.model_root = self.model_root.text().strip()
        self.state.storage.cache_root = self.cache_root.text().strip()
        if self.sound_root.text().strip():
            self.state.sound_library_path = self.sound_root.text().strip()
        self.state.settings['consolidate_imports'] = self.consolidate.isChecked()
        self.state.settings['autosave_enabled'] = self.recovery.isChecked()
        folders = ensure_project_folders(self.state)
        self.state.settings['project_folder'] = str(folders.root)
        self.state.touch()
        self.accept()
