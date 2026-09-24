from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QScrollArea, QSlider, QSpinBox, QStackedWidget, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget
)

from ..accessibility import AccessibilitySettings
from ..project import ProjectState, SourceAsset, ReferenceAsset
from ..storage import StorageSettings
from ..production_v2 import generate_three_previews, build_full_song, create_broker, run_full_auto_v2
from ..health import check_project
from ..export_v2 import ExportPlan, export_project
from ..versions import create_snapshot, list_snapshots
from ..stems import available_stem_engines
from ..youtube import fetch_oembed
from ..library import SoundLibrary
from ..master_v2 import master_v2
from ..lyrics_v2 import align_and_write, to_srt
from ..lyrics import to_lrc
from ..transcription import FasterWhisperTranscriber
from .studio import StudioWindow
from .player import PlayerBar
from .worker import FunctionThread
from .theme import stylesheet_for


class AccessibilityDialog(QDialog):
    def __init__(self, settings: AccessibilitySettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Accessibility")
        self.resize(520, 560)
        form = QFormLayout(self)

        self.ui_scale = QSpinBox(); self.ui_scale.setRange(100, 200); self.ui_scale.setSuffix("%"); self.ui_scale.setValue(settings.ui_scale)
        self.text_scale = QSpinBox(); self.text_scale.setRange(100, 200); self.text_scale.setSuffix("%"); self.text_scale.setValue(settings.text_scale)
        self.font = QComboBox(); self.font.addItems(["System", "Atkinson Hyperlegible Next", "OpenDyslexic"]); self.font.setCurrentText(settings.font_family)
        self.theme = QComboBox(); self.theme.addItems(["Dark", "Light", "High Contrast"]); self.theme.setCurrentText(settings.theme)
        self.density = QComboBox(); self.density.addItems(["Comfortable", "Compact"]); self.density.setCurrentText(settings.density)
        self.large = QCheckBox("Large controls"); self.large.setChecked(settings.large_controls)
        self.focus = QCheckBox("Enhanced focus indicators"); self.focus.setChecked(settings.enhanced_focus)
        self.motion = QCheckBox("Reduced motion"); self.motion.setChecked(settings.reduced_motion)
        self.reader = QCheckBox("Enhanced screen-reader feedback"); self.reader.setChecked(settings.enhanced_screen_reader)
        self.numeric = QCheckBox("Numeric meters"); self.numeric.setChecked(settings.numeric_meters)

        form.addRow("UI scale", self.ui_scale)
        form.addRow("Text scale", self.text_scale)
        form.addRow("Font", self.font)
        form.addRow("Theme", self.theme)
        form.addRow("Density", self.density)
        form.addRow(self.large)
        form.addRow(self.focus)
        form.addRow(self.motion)
        form.addRow(self.reader)
        form.addRow(self.numeric)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self):
        self.settings.ui_scale = self.ui_scale.value()
        self.settings.text_scale = self.text_scale.value()
        self.settings.font_family = self.font.currentText()
        self.settings.theme = self.theme.currentText()
        self.settings.density = self.density.currentText()
        self.settings.large_controls = self.large.isChecked()
        self.settings.enhanced_focus = self.focus.isChecked()
        self.settings.reduced_motion = self.motion.isChecked()
        self.settings.enhanced_screen_reader = self.reader.isChecked()
        self.settings.numeric_meters = self.numeric.isChecked()
        window = self.window()
        if window is not None:
            window.setStyleSheet(stylesheet_for(self.settings))
        super().accept()


class DashboardPage(QWidget):
    open_project_requested = Signal(str)

    def __init__(self, project: ProjectState, storage: StorageSettings, parent=None):
        super().__init__(parent); self.project=project; self.storage=storage
        root=QVBoxLayout(self)
        title=QLabel("PROJECT DASHBOARD"); title.setObjectName("PageTitle"); root.addWidget(title)
        subtitle=QLabel("Start simple, then move through Sources → References → Direction → Previews → Build → Master.")
        subtitle.setWordWrap(True); root.addWidget(subtitle)

        details=QGroupBox("Project")
        form=QFormLayout(details)
        self.name=QLineEdit(project.name)
        self.artist=QLineEdit(project.artist)
        self.start_mode=QComboBox(); self.start_mode.addItems(["Vocal / Acapella","Vocal + Stems","Full Song","Multiple Songs / Mashup","Instrumental","Lyrics Only","Empty Studio"])
        self.start_mode.setCurrentText(str(project.settings.get("start_mode","Vocal / Acapella")))
        self.root=QLineEdit(project.project_root or str(Path(storage.projects) / project.name))
        browse=QPushButton("Choose Folder"); browse.clicked.connect(self._browse)
        row=QHBoxLayout(); row.addWidget(self.root,1); row.addWidget(browse)
        form.addRow("Project name",self.name); form.addRow("Artist",self.artist); form.addRow("Start from",self.start_mode); form.addRow("Save location",row)
        root.addWidget(details)

        workflow=QGroupBox("Workflow Status")
        wf=QVBoxLayout(workflow)
        self.status=QLabel(); self.status.setWordWrap(True); wf.addWidget(self.status)
        root.addWidget(workflow)

        actions=QHBoxLayout()
        folder=QPushButton("Create/Open Project Folders"); folder.clicked.connect(self.create_folders)
        actions.addWidget(folder); actions.addStretch(1); root.addLayout(actions)

        recent_box=QGroupBox("Recent Projects")
        recent_layout=QVBoxLayout(recent_box)
        self.recent=QListWidget(); self.recent.itemDoubleClicked.connect(self._open_recent)
        recent_layout.addWidget(self.recent)
        recent_refresh=QPushButton("Refresh Recent Projects"); recent_refresh.clicked.connect(self.refresh_recent)
        recent_layout.addWidget(recent_refresh,0,Qt.AlignLeft)
        root.addWidget(recent_box,1)
        self.refresh_status(); self.refresh_recent()

    def _browse(self):
        path=QFileDialog.getExistingDirectory(self,"Choose project folder",self.root.text())
        if path:self.root.setText(path)

    def sync(self):
        self.project.name=self.name.text().strip() or "Untitled"
        self.project.artist=self.artist.text().strip()
        self.project.settings["start_mode"]=self.start_mode.currentText()
        self.project.project_root=self.root.text().strip()
        self.project.touch(); self.refresh_status()

    def create_folders(self):
        self.sync()
        folders=self.project.ensure_layout(self.project.project_root)
        self.root.setText(str(folders["root"]))
        QMessageBox.information(self,"Project Folders",f"Project folders ready:\n{folders['root']}")

    def refresh_recent(self):
        self.recent.clear()
        root=Path(self.storage.projects)
        if not root.is_dir():
            return
        paths=sorted(root.rglob("*.drellion"),key=lambda p:p.stat().st_mtime,reverse=True)[:30]
        for path in paths:
            self.recent.addItem(str(path))

    def _open_recent(self,item):
        path=item.text().strip()
        if path:
            self.open_project_requested.emit(path)

    def refresh_status(self):
        self.status.setText(
            f"Sources: {len(self.project.sources)}   |   "
            f"References: {len(self.project.references)} / 6   |   "
            f"Preview: {self.project.selected_preview or 'Not selected'}   |   "
            f"Build: {'Ready' if self.project.build_path else 'Not built'}   |   "
            f"Master: {'Ready' if self.project.master_path else 'Not mastered'}"
        )


class SourceRow(QGroupBox):
    ROLES = ["Lead Vocal", "Backing Vocal", "Full Song", "Instrumental", "Drums", "Bass", "Music", "Instrument", "Other"]

    def __init__(self, source: SourceAsset, parent=None):
        super().__init__(source.label or "Source", parent)
        self.source = source
        layout = QHBoxLayout(self)
        self.path = QLineEdit(source.path); self.path.setPlaceholderText("Drop or browse for an audio file")
        self.role = QComboBox(); self.role.addItems(self.ROLES); self.role.setCurrentText(source.role)
        self.preserve = QCheckBox("Preserve"); self.preserve.setChecked(source.preserve)
        self.rebuild = QCheckBox("Rebuild"); self.rebuild.setChecked(source.rebuild)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        layout.addWidget(self.path, 1); layout.addWidget(browse); layout.addWidget(self.role); layout.addWidget(self.preserve); layout.addWidget(self.rebuild)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose source", "", "Audio (*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.aiff)")
        if path:
            self.path.setText(path)
            self.setTitle(Path(path).name)

    def sync(self):
        self.source.path = self.path.text().strip()
        self.source.label = Path(self.source.path).name if self.source.path else self.title()
        self.source.role = self.role.currentText()
        self.source.preserve = self.preserve.isChecked()
        self.source.rebuild = self.rebuild.isChecked()


class SourcesPage(QWidget):
    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent)
        self.project = project
        outer = QVBoxLayout(self)
        title = QLabel("1  SOURCES"); title.setObjectName("PageTitle")
        outer.addWidget(title)
        help_text = QLabel("Add vocals, stems, a finished song, or several song parts. Preserve locks material you want Drellion to keep.")
        help_text.setWordWrap(True); outer.addWidget(help_text)
        self.rows_box = QVBoxLayout()
        outer.addLayout(self.rows_box)
        controls = QHBoxLayout()
        add = QPushButton("+ Add Source"); add.clicked.connect(self.add_source)
        split = QPushButton("Split Full Song Into Stems"); split.clicked.connect(self.split_full_song)
        controls.addWidget(add); controls.addWidget(split); controls.addStretch(1); outer.addLayout(controls)
        self.status = QLabel(""); outer.addWidget(self.status)
        self._workers = []
        outer.addStretch(1)
        self.refresh()

    def refresh(self):
        while self.rows_box.count():
            item = self.rows_box.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if not self.project.sources:
            self.project.add_source(role="Lead Vocal")
        for source in self.project.sources:
            self.rows_box.addWidget(SourceRow(source))

    def add_source(self):
        self.project.add_source()
        self.refresh()

    def split_full_song(self):
        self.sync()
        candidates = [s for s in self.project.sources if s.enabled and s.path and s.role in ("Full Song", "Instrumental")]
        if not candidates:
            QMessageBox.information(self, "Stem Separation", "Add a Full Song or Instrumental source first.")
            return
        choices = available_stem_engines()
        selected = next(((engine, status) for engine, status in choices if status.available), None)
        if selected is None:
            details = "\n".join(f"{status.name}: {status.detail}" for _, status in choices)
            QMessageBox.information(self, "Stem Separation", "No stem engine is installed.\n\n" + details)
            return
        engine, status = selected
        source = candidates[0]
        out = self.project.ensure_layout()["stems"] / Path(source.path).stem
        self.status.setText(f"Separating {Path(source.path).name} with {status.name}…")
        worker = FunctionThread(engine.separate, source.path, out)
        self._workers.append(worker)
        worker.completed.connect(lambda stems, w=worker: self._split_complete(stems, w))
        worker.failed.connect(lambda message, w=worker: self._split_failed(message, w))
        worker.start()

    def _split_complete(self, stems, worker):
        existing = dict(self.project.settings.get("generated_stems", {}) or {})
        existing.update(stems)
        self.project.settings["generated_stems"] = existing
        for role, path in stems.items():
            self.project.add_source(path=path, role=role.title(), label=Path(path).name)
        self.project.touch()
        self.status.setText(f"Created {len(stems)} stems.")
        self.refresh()
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()

    def _split_failed(self, message, worker):
        self.status.setText("Stem separation failed.")
        QMessageBox.critical(self, "Stem Separation", message)
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()

    def sync(self):
        for i in range(self.rows_box.count()):
            widget = self.rows_box.itemAt(i).widget()
            if isinstance(widget, SourceRow): widget.sync()


class ReferenceRow(QGroupBox):
    def __init__(self, reference: ReferenceAsset, number: int, parent=None):
        super().__init__(f"Reference {number}", parent)
        self.reference = reference
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.youtube = QLineEdit(reference.youtube_url); self.youtube.setPlaceholderText("YouTube URL")
        load_yt = QPushButton("Load Link"); load_yt.clicked.connect(self._load_youtube)
        self.path = QLineEdit(reference.path); self.path.setPlaceholderText("or local reference audio")
        browse = QPushButton("Browse"); browse.clicked.connect(self._browse)
        top.addWidget(self.youtube, 1); top.addWidget(load_yt); top.addWidget(self.path, 1); top.addWidget(browse)
        root.addLayout(top)
        second = QHBoxLayout()
        self.title = QLineEdit(reference.title); self.title.setPlaceholderText("Title")
        self.artist = QLineEdit(reference.artist); self.artist.setPlaceholderText("Artist")
        self.weight = QSlider(Qt.Horizontal); self.weight.setRange(0, 100); self.weight.setValue(round(reference.weight * 100))
        self.weight_value = QLabel(f"{self.weight.value()}%")
        self.weight.valueChanged.connect(lambda v: self.weight_value.setText(f"{v}%"))
        second.addWidget(self.title); second.addWidget(self.artist); second.addWidget(QLabel("Influence")); second.addWidget(self.weight); second.addWidget(self.weight_value)
        root.addLayout(second)

        matrix = QHBoxLayout()
        self.influence_boxes = {}
        for key in ("drums", "bass", "energy", "arrangement", "tone", "stereo", "master"):
            box = QCheckBox(key.title())
            box.setChecked(reference.influences.get(key, 1.0) > 0)
            self.influence_boxes[key] = box
            matrix.addWidget(box)
        matrix.addStretch(1)
        root.addLayout(matrix)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose reference", "", "Audio (*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.aiff)")
        if path: self.path.setText(path)

    def _load_youtube(self):
        try:
            meta = fetch_oembed(self.youtube.text().strip())
            self.title.setText(meta.title)
            self.artist.setText(meta.author)
            self.reference.youtube_url = meta.url
            self.reference.title = meta.title
            self.reference.artist = meta.author
        except Exception as exc:
            QMessageBox.warning(self, "YouTube Reference", str(exc))

    def sync(self):
        self.reference.youtube_url = self.youtube.text().strip()
        self.reference.path = self.path.text().strip()
        self.reference.title = self.title.text().strip()
        self.reference.artist = self.artist.text().strip()
        self.reference.weight = self.weight.value() / 100.0
        for key, box in self.influence_boxes.items():
            self.reference.influences[key] = 1.0 if box.isChecked() else 0.0


class ReferencesPage(QWidget):
    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent)
        self.project = project
        outer = QVBoxLayout(self)
        title = QLabel("2  REFERENCE BOARD"); title.setObjectName("PageTitle")
        outer.addWidget(title)
        text = QLabel("Blend up to six reference songs. Each reference can guide different production characteristics without becoming source audio.")
        text.setWordWrap(True); outer.addWidget(text)
        self.rows_box = QVBoxLayout(); outer.addLayout(self.rows_box)
        row = QHBoxLayout()
        add = QPushButton("+ Add Reference"); add.clicked.connect(self.add_reference)
        balance = QPushButton("Auto Balance"); balance.clicked.connect(self.auto_balance)
        row.addWidget(add); row.addWidget(balance); row.addStretch(1); outer.addLayout(row)
        outer.addStretch(1)
        self.refresh()

    def refresh(self):
        while self.rows_box.count():
            item = self.rows_box.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for i, reference in enumerate(self.project.references[:6], 1):
            self.rows_box.addWidget(ReferenceRow(reference, i))

    def add_reference(self):
        if len(self.project.references) >= 6:
            QMessageBox.information(self, "Reference Board", "Auto mode supports six reference slots. Additional references are available in Studio.")
            return
        self.project.add_reference()
        self.refresh()

    def auto_balance(self):
        if not self.project.references: return
        value = 1.0 / len(self.project.references)
        for ref in self.project.references: ref.weight = value
        self.refresh()

    def sync(self):
        for i in range(self.rows_box.count()):
            widget = self.rows_box.itemAt(i).widget()
            if isinstance(widget, ReferenceRow): widget.sync()


class DirectionPage(QWidget):
    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent); self.project = project
        form = QFormLayout(self)
        title = QLabel("3  DIRECTION"); title.setObjectName("PageTitle"); form.addRow(title)
        self.engine = QComboBox()
        self.engine.addItem("Automatic", "auto")
        self.engine.addItem("ACE-Step 1.5 (HTTP / local server / remote server)", "ace-step-http")
        self.engine.addItem("DiffRhythm 2 Local", "diffrhythm-local")
        saved_engine = str(project.settings.get("engine_id", "auto"))
        saved_index = self.engine.findData(saved_engine)
        if saved_index >= 0: self.engine.setCurrentIndex(saved_index)
        self.reference = QSlider(Qt.Horizontal); self.reference.setRange(0,100); self.reference.setValue(int(project.settings.get("reference_strength", 80)))
        self.vocal = QComboBox(); self.vocal.addItems(["Natural", "Polished", "Flexible"]); self.vocal.setCurrentText(project.vocal_preservation)
        self.style = QTextEdit(); self.style.setPlaceholderText("Describe the production direction: anthemic, dark, cinematic, punchy drums, sparse verse...")
        form.addRow("Generation engine", self.engine)
        form.addRow("Reference strength", self.reference)
        form.addRow("Vocal handling", self.vocal)
        form.addRow("Production direction", self.style)

    def sync(self):
        self.project.settings["engine_id"] = self.engine.currentData()
        self.project.settings["reference_strength"] = self.reference.value()
        self.project.settings["production_direction"] = self.style.toPlainText()
        self.project.vocal_preservation = self.vocal.currentText()


class PreviewsPage(QWidget):
    play_requested = Signal(str, str)

    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent)
        self.project = project
        self.candidates = []
        self._workers = []
        root = QVBoxLayout(self)
        title = QLabel("4  PREVIEWS"); title.setObjectName("PageTitle"); root.addWidget(title)
        info = QLabel("Generate three real 20–30 second arrangements. Every preview must pass Drellion QC before it is marked ready.")
        info.setWordWrap(True); root.addWidget(info)
        self.status = QLabel("No previews generated."); root.addWidget(self.status)
        self.list = QVBoxLayout(); root.addLayout(self.list)
        self.generate = QPushButton("Generate 3 Previews"); self.generate.setObjectName("Primary"); self.generate.clicked.connect(self.generate_previews)
        root.addWidget(self.generate, 0, Qt.AlignLeft)
        root.addStretch(1)

    def _clear(self):
        while self.list.count():
            item = self.list.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def generate_previews(self):
        self.generate.setEnabled(False)
        self.status.setText("Generating previews with the selected engine…")
        out = self.project.ensure_layout()["previews"]
        worker = FunctionThread(generate_three_previews, self.project, out)
        self._workers.append(worker)
        worker.completed.connect(lambda result, w=worker: self._complete(result, w))
        worker.failed.connect(lambda message, w=worker: self._failed(message, w))
        worker.start()

    def show_candidates(self, candidates):
        self.candidates = candidates
        self._clear()
        accepted = 0
        for candidate in candidates:
            box = QGroupBox(candidate.name)
            row = QHBoxLayout(box)
            state = "PASS" if candidate.accepted else "REJECTED"
            if candidate.accepted: accepted += 1
            row.addWidget(QLabel(f"{state} · {candidate.provider_id} · seed {candidate.seed}"))
            play = QPushButton("Play Together"); play.clicked.connect(lambda checked=False, c=candidate: self.play_requested.emit(c.name, c.audio_path))
            select = QPushButton("Select"); select.setEnabled(candidate.accepted); select.clicked.connect(lambda checked=False, c=candidate: self.select_candidate(c))
            row.addWidget(play); row.addWidget(select)
            self.list.addWidget(box)
        self.status.setText(f"{accepted} of {len(candidates)} previews passed QC.")

    def _complete(self, candidates, worker):
        self.show_candidates(candidates)
        self.generate.setEnabled(True)
        if worker in self._workers: self._workers.remove(worker)
        worker.deleteLater()

    def _failed(self, message, worker):
        self.status.setText("Generation failed.")
        self.generate.setEnabled(True)
        QMessageBox.critical(self, "Preview generation failed", message)
        if worker in self._workers: self._workers.remove(worker)
        worker.deleteLater()

    def select_candidate(self, candidate):
        self.project.selected_preview = candidate.name
        self.project.settings["selected_preview_seed"] = candidate.seed
        self.project.settings["selected_preview_provider"] = candidate.provider_id
        self.project.settings["selected_preview_path"] = candidate.audio_path
        self.project.touch()
        self.status.setText(f"Selected {candidate.name}.")


class BuildPage(QWidget):
    play_requested = Signal(str, str)

    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent)
        self.project = project
        self._workers = []
        root = QVBoxLayout(self)
        title = QLabel("5  BUILD"); title.setObjectName("PageTitle"); root.addWidget(title)
        text = QLabel("Build the chosen arrangement using the selected real generation provider. Drellion will not silently switch to the Basic Test Engine.")
        text.setWordWrap(True); root.addWidget(text)
        self.status = QLabel("Select a passing preview first."); root.addWidget(self.status)
        self.button = QPushButton("Build Full Song"); self.button.setObjectName("Primary"); self.button.clicked.connect(self.build)
        root.addWidget(self.button, 0, Qt.AlignLeft)
        self.play = QPushButton("Play Build"); self.play.setEnabled(False); self.play.clicked.connect(self.play_build); root.addWidget(self.play, 0, Qt.AlignLeft)
        root.addStretch(1)

    def build(self):
        seed = self.project.settings.get("selected_preview_seed")
        if not self.project.selected_preview or seed is None:
            QMessageBox.information(self, "Build", "Select a preview that passed QC first.")
            return
        self.button.setEnabled(False)
        self.status.setText("Building the full arrangement…")
        out = self.project.ensure_layout()["generated"]
        worker = FunctionThread(build_full_song, self.project, out, seed)
        self._workers.append(worker)
        worker.completed.connect(lambda result, w=worker: self._complete(result, w))
        worker.failed.connect(lambda message, w=worker: self._failed(message, w))
        worker.start()

    def _complete(self, result, worker):
        self.project.build_path = result.audio_path
        self.project.settings["build_provider"] = result.provider_id
        self.project.settings["build_report"] = result.metadata_path
        self.project.touch()
        self.status.setText(f"Build ready · {result.provider_id}")
        self.button.setEnabled(True); self.play.setEnabled(True)
        if worker in self._workers: self._workers.remove(worker)
        worker.deleteLater()

    def _failed(self, message, worker):
        self.status.setText("Build failed.")
        self.button.setEnabled(True)
        QMessageBox.critical(self, "Build failed", message)
        if worker in self._workers: self._workers.remove(worker)
        worker.deleteLater()

    def play_build(self):
        if self.project.build_path:
            self.play_requested.emit("Build", self.project.build_path)


class PlaceholderPage(QWidget):
    def __init__(self, title: str, body: str, buttons: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        h = QLabel(title); h.setObjectName("PageTitle"); layout.addWidget(h)
        text = QLabel(body); text.setWordWrap(True); layout.addWidget(text)
        for label in buttons or []:
            button = QPushButton(label)
            if label.startswith("Generate") or label.startswith("Build") or label.startswith("Master") or label.startswith("Export"):
                button.setObjectName("Primary")
            layout.addWidget(button, 0, Qt.AlignLeft)
        layout.addStretch(1)


class StoragePage(QWidget):
    def __init__(self, storage: StorageSettings, parent=None):
        super().__init__(parent); self.storage = storage
        form = QFormLayout(self)
        title = QLabel("STORAGE & FILE LOCATIONS"); title.setObjectName("PageTitle"); form.addRow(title)
        self.fields = {}
        for key in ("projects", "sound_library", "models", "cache", "exports"):
            edit = QLineEdit(getattr(storage, key)); self.fields[key] = edit
            button = QPushButton("Browse")
            button.clicked.connect(lambda checked=False, e=edit: self._browse(e))
            row = QHBoxLayout(); row.addWidget(edit,1); row.addWidget(button)
            form.addRow(key.replace("_"," ").title(), row)

    def _browse(self, edit):
        path = QFileDialog.getExistingDirectory(self, "Choose folder", edit.text())
        if path: edit.setText(path)

    def sync(self):
        for key, edit in self.fields.items():
            setattr(self.storage, key, edit.text().strip())


class MasterPage(QWidget):
    play_requested = Signal(str, str)

    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent); self.project=project; self._workers=[]
        root=QVBoxLayout(self)
        title=QLabel("6  MASTER"); title.setObjectName("PageTitle"); root.addWidget(title)
        form=QFormLayout()
        self.lufs=QComboBox(); self.lufs.addItems(["-14","-12","-10","-9","-8"]); self.lufs.setCurrentText(str(project.settings.get("target_lufs",-14)))
        self.punch=QSlider(Qt.Horizontal); self.punch.setRange(0,100); self.punch.setValue(int(project.settings.get("master_punch",50)))
        self.width=QSlider(Qt.Horizontal); self.width.setRange(0,100); self.width.setValue(int(project.settings.get("master_width",50)))
        self.ref=QSlider(Qt.Horizontal); self.ref.setRange(0,100); self.ref.setValue(int(project.settings.get("master_reference_strength",70)))
        form.addRow("Target LUFS",self.lufs); form.addRow("Punch",self.punch); form.addRow("Width",self.width); form.addRow("Reference match",self.ref)
        root.addLayout(form)
        self.status=QLabel("Ready when a build or finished song exists."); root.addWidget(self.status)
        row=QHBoxLayout()
        master=QPushButton("Master Track"); master.setObjectName("Primary"); master.clicked.connect(self.master)
        self.play=QPushButton("Play Master"); self.play.setEnabled(bool(project.master_path)); self.play.clicked.connect(self.play_master)
        row.addWidget(master); row.addWidget(self.play); row.addStretch(1); root.addLayout(row); root.addStretch(1)
        self.master_button=master

    def master(self):
        self.project.settings["target_lufs"]=float(self.lufs.currentText())
        self.project.settings["master_punch"]=self.punch.value()
        self.project.settings["master_width"]=self.width.value()
        self.project.settings["master_reference_strength"]=self.ref.value()
        self.master_button.setEnabled(False); self.status.setText("Mastering with blended references…")
        out=self.project.ensure_layout()["masters"]
        worker=FunctionThread(master_v2,self.project,out); self._workers.append(worker)
        worker.completed.connect(lambda path,w=worker:self._complete(path,w))
        worker.failed.connect(lambda message,w=worker:self._failed(message,w)); worker.start()

    def _complete(self,path,worker):
        self.master_button.setEnabled(True); self.play.setEnabled(True); self.status.setText(f"Master ready: {Path(path).name}")
        if worker in self._workers:self._workers.remove(worker)
        worker.deleteLater()

    def _failed(self,message,worker):
        self.master_button.setEnabled(True); self.status.setText("Master failed.")
        QMessageBox.critical(self,"Master failed",message)
        if worker in self._workers:self._workers.remove(worker)
        worker.deleteLater()

    def play_master(self):
        if self.project.master_path:self.play_requested.emit("Master",self.project.master_path)


class StudioLauncherPage(QWidget):
    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent); self.project=project; self.studio=None
        root=QVBoxLayout(self)
        title=QLabel("CUSTOM STUDIO"); title.setObjectName("PageTitle"); root.addWidget(title)
        text=QLabel("Open the multitrack non-destructive Studio for clips, tracks, fades, gain, pan, mute/solo, splitting and rendered mixes.")
        text.setWordWrap(True); root.addWidget(text)
        button=QPushButton("Open Studio"); button.setObjectName("Primary"); button.clicked.connect(self.open_studio); root.addWidget(button,0,Qt.AlignLeft)
        root.addStretch(1)

    def open_studio(self):
        main=self.window()
        if not hasattr(main,"project"):
            QMessageBox.warning(self,"Studio","Project context unavailable.")
            return
        self.studio=StudioWindow(main); self.studio.show()


class LibraryPage(QWidget):
    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent); self.project=project; self.library=None
        root=QVBoxLayout(self)
        title=QLabel("SOUND LIBRARY"); title.setObjectName("PageTitle"); root.addWidget(title)
        row=QHBoxLayout()
        self.path=QLineEdit(project.sound_library_path); self.path.setPlaceholderText("Sound library folder")
        browse=QPushButton("Browse"); browse.clicked.connect(self._browse)
        refresh=QPushButton("Refresh"); refresh.clicked.connect(self.refresh)
        row.addWidget(self.path,1); row.addWidget(browse); row.addWidget(refresh); root.addLayout(row)
        searchrow=QHBoxLayout()
        self.search=QLineEdit(); self.search.setPlaceholderText("Search sounds")
        searchbutton=QPushButton("Search"); searchbutton.clicked.connect(self.run_search)
        searchrow.addWidget(self.search,1); searchrow.addWidget(searchbutton); root.addLayout(searchrow)
        self.status=QLabel("Choose or refresh a library."); root.addWidget(self.status)
        self.list=QListWidget(); root.addWidget(self.list,1)

    def _browse(self):
        path=QFileDialog.getExistingDirectory(self,"Choose sound library",self.path.text())
        if path:self.path.setText(path); self.refresh()

    def refresh(self):
        root=self.path.text().strip()
        if not root:return
        self.project.sound_library_path=root
        self.library=SoundLibrary(root)
        items=self.library.scan()
        self.project.settings["sound_count"]=len(items)
        self.project.touch()
        self._show(items)
        self.status.setText(f"{len(items):,} sounds indexed.")

    def run_search(self):
        if self.library is None:self.refresh()
        if self.library is None:return
        items=self.library.search(self.search.text(),limit=500)
        self._show(items); self.status.setText(f"{len(items):,} matches.")

    def _show(self,items):
        self.list.clear()
        for item in items[:500]:self.list.addItem(f"{item.name}  [{item.extension}]")


class ExportPage(QWidget):
    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent); self.project=project; self._workers=[]
        root=QVBoxLayout(self)
        title=QLabel("EXPORT CENTER"); title.setObjectName("PageTitle"); root.addWidget(title)

        song=QGroupBox("Song formats"); sl=QHBoxLayout(song)
        self.formats={}
        for key,label,checked in (("wav","Master WAV",True),("mp3","MP3",True),("flac","FLAC",False),("m4a","M4A",False),("mp4","MP4 Video",False)):
            box=QCheckBox(label); box.setChecked(checked); self.formats[key]=box; sl.addWidget(box)
        root.addWidget(song)

        options=QGroupBox("Package"); ol=QHBoxLayout(options)
        self.stems=QCheckBox("Stems"); self.stems.setChecked(True)
        self.lrc=QCheckBox("Lyrics LRC"); self.lrc.setChecked(True)
        self.srt=QCheckBox("Lyrics SRT")
        self.archive=QCheckBox("Project Archive")
        for box in (self.stems,self.lrc,self.srt,self.archive): ol.addWidget(box)
        root.addWidget(options)

        row=QHBoxLayout()
        self.location=QLineEdit(project.export_root); self.location.setPlaceholderText("Export folder")
        browse=QPushButton("Browse"); browse.clicked.connect(self._browse)
        row.addWidget(self.location,1); row.addWidget(browse); root.addLayout(row)

        self.status=QLabel("Ready."); root.addWidget(self.status)
        self.button=QPushButton("EXPORT ALL"); self.button.setObjectName("Primary"); self.button.clicked.connect(self.export)
        root.addWidget(self.button,0,Qt.AlignLeft); root.addStretch(1)

    def _browse(self):
        path=QFileDialog.getExistingDirectory(self,"Choose export folder",self.location.text())
        if path: self.location.setText(path)

    def export(self):
        destination=self.location.text().strip() or self.project.ensure_layout()["exports"]
        self.project.export_root=str(destination)
        formats=[key for key,box in self.formats.items() if box.isChecked()]
        if not formats:
            QMessageBox.information(self,"Export","Choose at least one song format.")
            return
        plan=ExportPlan(formats=formats,export_stems=self.stems.isChecked(),lyrics_lrc=self.lrc.isChecked(),lyrics_srt=self.srt.isChecked(),project_archive=self.archive.isChecked())
        self.button.setEnabled(False); self.status.setText("Exporting…")
        worker=FunctionThread(export_project,self.project,destination,plan); self._workers.append(worker)
        worker.completed.connect(lambda outputs,w=worker:self._complete(outputs,w))
        worker.failed.connect(lambda message,w=worker:self._failed(message,w)); worker.start()

    def _complete(self,outputs,worker):
        self.button.setEnabled(True); self.status.setText(f"Exported {len(outputs)} files to {self.project.export_root}")
        if worker in self._workers:self._workers.remove(worker)
        worker.deleteLater()

    def _failed(self,message,worker):
        self.button.setEnabled(True); self.status.setText("Export failed.")
        QMessageBox.critical(self,"Export failed",message)
        if worker in self._workers:self._workers.remove(worker)
        worker.deleteLater()


class LyricsPage(QWidget):
    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent); self.project=project; self._workers=[]
        root=QVBoxLayout(self)
        title=QLabel("LYRICS & TIMING"); title.setObjectName("PageTitle"); root.addWidget(title)
        note=QLabel("Paste lyrics, align them to the lead vocal, or transcribe with the optional faster-whisper model pack.")
        note.setWordWrap(True); root.addWidget(note)
        self.editor=QTextEdit(); self.editor.setPlainText(project.lyrics); self.editor.setPlaceholderText("Paste or type lyrics here…")
        root.addWidget(self.editor,1)
        row=QHBoxLayout()
        save=QPushButton("Save Lyrics"); save.clicked.connect(self.sync)
        align=QPushButton("Align + Create LRC/SRT"); align.clicked.connect(self.align)
        transcribe=QPushButton("Transcribe Lead Vocal"); transcribe.clicked.connect(self.transcribe)
        row.addWidget(save); row.addWidget(align); row.addWidget(transcribe); row.addStretch(1); root.addLayout(row)
        self.status=QLabel(""); root.addWidget(self.status)

    def _vocal_path(self):
        for source in self.project.sources:
            if source.enabled and source.path and source.role=="Lead Vocal":
                return source.path
        return self.project.vocal.path

    def sync(self):
        self.project.lyrics=self.editor.toPlainText()
        self.project.touch()
        self.status.setText("Lyrics saved in project.")

    def align(self):
        self.sync()
        vocal=self._vocal_path()
        if not vocal:
            QMessageBox.information(self,"Lyrics","Add a lead vocal first.")
            return
        out=self.project.ensure_layout()["lyrics"]
        try:
            cues,lrc,srt=align_and_write(self.project.lyrics,vocal,out)
            self.project.settings["lyrics_lrc_path"]=str(lrc)
            self.project.settings["lyrics_srt_path"]=str(srt)
            self.project.settings["lyrics_cue_count"]=len(cues)
            self.project.touch()
            self.status.setText(f"Aligned {len(cues)} lyric cues.")
        except Exception as exc:
            QMessageBox.critical(self,"Lyric alignment failed",str(exc))

    def transcribe(self):
        vocal=self._vocal_path()
        if not vocal:
            QMessageBox.information(self,"Transcription","Add a lead vocal first.")
            return
        transcriber=FasterWhisperTranscriber()
        if not transcriber.available():
            QMessageBox.information(self,"Transcription","faster-whisper is not installed. The normal lyric alignment tools still work.")
            return
        self.status.setText("Transcribing…")
        worker=FunctionThread(transcriber.transcribe,vocal,str(self.project.settings.get("whisper_model","small")))
        self._workers.append(worker)
        worker.completed.connect(lambda result,w=worker:self._transcribed(result,w))
        worker.failed.connect(lambda message,w=worker:self._transcribe_failed(message,w)); worker.start()

    def _transcribed(self,result,worker):
        self.editor.setPlainText(result.text)
        self.project.lyrics=result.text
        out=self.project.ensure_layout()["lyrics"]
        lrc=out/"lyrics-whisper.lrc"; lrc.write_text(to_lrc(result.cues),encoding="utf-8")
        srt=out/"lyrics-whisper.srt"; srt.write_text(to_srt(result.cues),encoding="utf-8")
        self.project.settings["lyrics_lrc_path"]=str(lrc)
        self.project.settings["lyrics_srt_path"]=str(srt)
        self.project.settings["lyrics_language"]=result.language
        self.project.touch()
        self.status.setText(f"Transcribed {len(result.cues)} timed words/cues.")
        if worker in self._workers:self._workers.remove(worker)
        worker.deleteLater()

    def _transcribe_failed(self,message,worker):
        self.status.setText("Transcription failed.")
        QMessageBox.critical(self,"Transcription failed",message)
        if worker in self._workers:self._workers.remove(worker)
        worker.deleteLater()


class V2Workspace(QWidget):
    open_project_requested = Signal(str)

    NAV = [
        ("Dashboard", 0), ("Sources", 1), ("References", 2), ("Direction", 3), ("Previews", 4),
        ("Build", 5), ("Master", 6), ("Studio", 7), ("Library", 8),
        ("Export", 9), ("Versions", 10), ("Storage", 11), ("AI Engines", 12), ("Project Health", 13), ("Lyrics & Timing", 14),
    ]

    def __init__(self, project: ProjectState, storage: StorageSettings, accessibility: AccessibilitySettings, parent=None):
        super().__init__(parent)
        self.project=project; self.storage=storage; self.accessibility=accessibility; self._workers=[]
        root=QVBoxLayout(self)
        header=QHBoxLayout()
        brand=QLabel("DRELLION NEXUS 2.0"); brand.setStyleSheet("font-size:20pt;font-weight:800;"); header.addWidget(brand)
        header.addStretch(1)
        self.project_label=QLabel(project.name); header.addWidget(self.project_label)
        self.auto_button=QPushButton("AI AUTO"); self.auto_button.setObjectName("Primary"); self.auto_button.clicked.connect(self.run_auto); header.addWidget(self.auto_button)
        accessibility_button=QPushButton("♿ Accessibility"); accessibility_button.clicked.connect(self.open_accessibility); header.addWidget(accessibility_button)
        root.addLayout(header)

        body=QHBoxLayout()
        nav=QVBoxLayout()
        self.nav_buttons=[]
        for label,index in self.NAV:
            button=QPushButton(label); button.setCheckable(True); button.clicked.connect(lambda checked=False,i=index:self.goto(i))
            nav.addWidget(button); self.nav_buttons.append(button)
        nav.addStretch(1)
        nav_widget=QWidget(); nav_widget.setLayout(nav); nav_widget.setFixedWidth(190)
        body.addWidget(nav_widget)

        self.stack=QStackedWidget()
        self.dashboard=DashboardPage(project,storage); self.dashboard.open_project_requested.connect(self.open_project_requested.emit); self.stack.addWidget(self.dashboard)
        self.sources=SourcesPage(project); self.references=ReferencesPage(project); self.direction=DirectionPage(project)
        self.stack.addWidget(self.sources)
        self.stack.addWidget(self.references)
        self.stack.addWidget(self.direction)
        self.previews = PreviewsPage(project); self.previews.play_requested.connect(self.play_audio); self.stack.addWidget(self.previews)
        self.build_page = BuildPage(project); self.build_page.play_requested.connect(self.play_audio); self.stack.addWidget(self.build_page)
        self.master_page=MasterPage(project); self.master_page.play_requested.connect(self.play_audio); self.stack.addWidget(self.master_page)
        self.studio_page=StudioLauncherPage(project); self.stack.addWidget(self.studio_page)
        self.library_page=LibraryPage(project); self.stack.addWidget(self.library_page)
        self.stack.addWidget(ExportPage(project))
        self.versions_page=VersionsPage(project); self.stack.addWidget(self.versions_page)
        self.storage_page=StoragePage(storage); self.stack.addWidget(self.storage_page)
        self.engines_page=EnginesPage(project); self.stack.addWidget(self.engines_page)
        self.health_page=HealthPage(project); self.stack.addWidget(self.health_page)
        self.lyrics_page=LyricsPage(project); self.stack.addWidget(self.lyrics_page)
        body.addWidget(self.stack,1)
        root.addLayout(body,1)
        self.player = PlayerBar(self)
        root.addWidget(self.player)
        self.goto(0)

    def goto(self,index:int):
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav_buttons): b.setChecked(i==index)

    def sync(self):
        self.dashboard.sync(); self.sources.sync(); self.references.sync(); self.direction.sync(); self.lyrics_page.sync(); self.storage_page.sync(); self.engines_page.sync()

    def run_auto(self):
        self.sync()
        self.auto_button.setEnabled(False)
        self.auto_button.setText("AI AUTO — RUNNING")
        root=self.project.ensure_layout()["root"]
        worker=FunctionThread(run_full_auto_v2,self.project,root)
        self._workers.append(worker)
        worker.completed.connect(lambda result,w=worker:self._auto_complete(result,w))
        worker.failed.connect(lambda message,w=worker:self._auto_failed(message,w))
        worker.start()

    def _auto_complete(self,result,worker):
        self.previews.show_candidates(result.previews)
        self.build_page.status.setText(f"Build ready · {result.build.provider_id}")
        self.build_page.play.setEnabled(True)
        self.master_page.status.setText(f"Master ready: {Path(result.master_path).name}")
        self.master_page.play.setEnabled(True)
        self.player.set_sources({
            "Selected Preview": result.selected.audio_path,
            "Build": result.build.audio_path,
            "Master": result.master_path,
        },preferred="Master")
        self.dashboard.refresh_status()
        self.auto_button.setEnabled(True); self.auto_button.setText("AI AUTO")
        if worker in self._workers:self._workers.remove(worker)
        worker.deleteLater()
        QMessageBox.information(self,"AI Auto complete",f"Selected {result.selected.name}\nBuild and master are ready.")

    def _auto_failed(self,message,worker):
        self.auto_button.setEnabled(True); self.auto_button.setText("AI AUTO")
        if worker in self._workers:self._workers.remove(worker)
        worker.deleteLater()
        QMessageBox.critical(self,"AI Auto failed",message)

    def play_audio(self, label: str, path: str):
        self.player.set_sources({label: path}, preferred=label)

    def open_accessibility(self):
        dialog=AccessibilityDialog(self.accessibility,self)
        dialog.exec()
