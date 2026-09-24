from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox,
    QPushButton, QVBoxLayout,
)

from ..versions import create_version, list_versions, load_version


class VersionsDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent or main)
        self.main = main
        self.setWindowTitle('Drellion Nexus — Versions')
        self.resize(700, 620)

        outer = QVBoxLayout(self)
        title = QLabel('PROJECT VERSIONS')
        title.setStyleSheet('font-size:18pt;font-weight:700;')
        outer.addWidget(title)
        note = QLabel('Named snapshots live in the project Versions folder and do not overwrite your current project.')
        note.setWordWrap(True)
        note.setObjectName('Muted')
        outer.addWidget(note)

        self.list = QListWidget()
        outer.addWidget(self.list, 1)

        row = QHBoxLayout()
        create = QPushButton('Create Snapshot')
        create.clicked.connect(self.create)
        restore = QPushButton('Restore Selected')
        restore.clicked.connect(self.restore)
        folder = QPushButton('Show File Path')
        folder.clicked.connect(self.show_path)
        row.addWidget(create)
        row.addWidget(restore)
        row.addWidget(folder)
        row.addStretch(1)
        close = QPushButton('Close')
        close.clicked.connect(self.accept)
        row.addWidget(close)
        outer.addLayout(row)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for path in list_versions(self.main.project, self.main.project_path):
            self.list.addItem(str(path))

    def create(self):
        label, ok = QInputDialog.getText(self, 'Create Snapshot', 'Snapshot name:')
        if not ok or not label.strip():
            return
        path = create_version(self.main.project, label.strip(), project_path=self.main.project_path)
        self.main.snapshot('Created named version')
        self.refresh()
        QMessageBox.information(self, 'Version created', str(path))

    def selected(self) -> Path | None:
        item = self.list.currentItem()
        return Path(item.text()) if item else None

    def restore(self):
        path = self.selected()
        if path is None:
            QMessageBox.information(self, 'Restore Version', 'Select a version first.')
            return
        answer = QMessageBox.question(
            self,
            'Restore Version',
            'Restore this snapshot into the current editor? The current project file is not deleted.',
        )
        if answer != QMessageBox.Yes:
            return
        self.main.project = load_version(path)
        self.main.history.push('Restored named version', self.main.project)
        self.main.sync_ui_from_project()
        self.accept()

    def show_path(self):
        path = self.selected()
        if path is not None:
            QMessageBox.information(self, 'Version Path', str(path))
