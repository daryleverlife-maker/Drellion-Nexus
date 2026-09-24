from __future__ import annotations

from pathlib import Path
import shutil

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from ..exporter import PRESETS, export_audio
from ..storage import ensure_project_folders
from ..timeline import render_all_stems, sync_generated_tracks


class ExportCenterDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent or main)
        self.main = main
        self.project = main.project
        self.setWindowTitle('Drellion Nexus — Export Center')
        self.resize(700, 720)

        outer = QVBoxLayout(self)
        title = QLabel('EXPORT CENTER')
        title.setStyleSheet('font-size:18pt;font-weight:700;')
        outer.addWidget(title)
        intro = QLabel(
            'Export the finished song, premaster and separate stems from one place. '
            'Nothing here overwrites source media.'
        )
        intro.setWordWrap(True)
        intro.setObjectName('Muted')
        outer.addWidget(intro)

        format_card = QFrame()
        format_card.setObjectName('Card')
        fl = QVBoxLayout(format_card)
        fl.addWidget(QLabel('SONG FORMAT'))
        self.format = QComboBox()
        self.format.addItems(PRESETS.keys())
        self.format.setCurrentText('WAV 24-bit')
        fl.addWidget(self.format)
        outer.addWidget(format_card)

        outputs = QFrame()
        outputs.setObjectName('Card')
        ol = QVBoxLayout(outputs)
        ol.addWidget(QLabel('DELIVERABLES'))
        self.master = QCheckBox('Master')
        self.master.setChecked(True)
        self.premaster = QCheckBox('Premaster / Build')
        self.instrumental = QCheckBox('Generated instrumental (when available)')
        self.vocal = QCheckBox('Original vocal')
        self.stems = QCheckBox('All Studio stems')
        self.stems.setChecked(True)
        self.project_archive = QCheckBox('Copy .drellion project file into export folder')
        for widget in (self.master, self.premaster, self.instrumental, self.vocal, self.stems, self.project_archive):
            ol.addWidget(widget)
        outer.addWidget(outputs)

        folder_card = QFrame()
        folder_card.setObjectName('Card')
        folder_layout = QVBoxLayout(folder_card)
        folder_layout.addWidget(QLabel('EXPORT LOCATION'))
        row = QHBoxLayout()
        folders = ensure_project_folders(self.project, self.main.project_path)
        default = self.project.storage.export_root or str(folders.exports)
        self.location = QLabel(default)
        self.location.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.location, 1)
        choose = QPushButton('Change…')
        choose.clicked.connect(self.choose_folder)
        row.addWidget(choose)
        folder_layout.addLayout(row)
        outer.addWidget(folder_card)
        outer.addStretch(1)

        bottom = QHBoxLayout()
        close = QPushButton('Close')
        close.clicked.connect(self.reject)
        export = QPushButton('EXPORT SELECTED')
        export.setObjectName('Primary')
        export.clicked.connect(self.export)
        bottom.addStretch(1)
        bottom.addWidget(close)
        bottom.addWidget(export)
        outer.addLayout(bottom)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Export Folder', self.location.text())
        if path:
            self.location.setText(path)
            self.project.storage.export_root = path
            self.project.touch()

    def _export_one(self, source: str, stem: str, root: Path) -> Path:
        preset_name = self.format.currentText()
        return export_audio(source, root / stem, preset_name)

    def export(self):
        root = Path(self.location.text().strip())
        root.mkdir(parents=True, exist_ok=True)
        made: list[Path] = []
        try:
            if self.master.isChecked() and self.project.master_path:
                made.append(self._export_one(self.project.master_path, f'{self.project.name} - Master', root))
            if self.premaster.isChecked() and self.project.build_path:
                made.append(self._export_one(self.project.build_path, f'{self.project.name} - Premaster', root))
            instrumental = str(self.project.settings.get('generated_instrumental', '') or '')
            if self.instrumental.isChecked() and instrumental and Path(instrumental).is_file():
                made.append(self._export_one(instrumental, f'{self.project.name} - Instrumental', root))
            if self.vocal.isChecked() and self.project.vocal.path and Path(self.project.vocal.path).is_file():
                made.append(self._export_one(self.project.vocal.path, f'{self.project.name} - Vocal', root))
            if self.stems.isChecked():
                sync_generated_tracks(self.project)
                made.extend(render_all_stems(self.project, root / 'Stems'))
            if self.project_archive.isChecked() and self.main.project_path and Path(self.main.project_path).is_file():
                target = root / Path(self.main.project_path).name
                shutil.copy2(self.main.project_path, target)
                made.append(target)
            self.project.settings['last_export_folder'] = str(root)
            self.main.snapshot('Exported delivery package')
            QMessageBox.information(
                self, 'Export complete',
                f'Created {len(made)} file(s) in:\n{root}'
            )
        except Exception as exc:
            QMessageBox.critical(self, 'Export failed', str(exc))
