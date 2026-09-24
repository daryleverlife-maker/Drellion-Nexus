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
from ..production_v2 import generate_three_previews, build_full_song, create_broker
from ..health import check_project
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


class SourceRow(QGroupBox):
    ROLES = ["Lead Vocal", "Backing Vocal", "Drums", "Bass", "Music", "Instrument", "Other"]

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
        controls.addWidget(add); controls.addStretch(1); outer.addLayout(controls)
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
        self.path = QLineEdit(reference.path); self.path.setPlaceholderText("or local reference audio")
        browse = QPushButton("Browse"); browse.clicked.connect(self._browse)
        top.addWidget(self.youtube, 1); top.addWidget(self.path, 1); top.addWidget(browse)
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
        self.engine = QComboBox(); self.engine.addItems(["Automatic", "ACE-Step Online", "ACE-Step Local", "DiffRhythm Online", "DiffRhythm Local", "YuE", "Basic Test Engine"])
        self.reference = QSlider(Qt.Horizontal); self.reference.setRange(0,100); self.reference.setValue(int(project.settings.get("reference_strength", 80)))
        self.vocal = QComboBox(); self.vocal.addItems(["Natural", "Polished", "Flexible"]); self.vocal.setCurrentText(project.vocal_preservation)
        self.style = QTextEdit(); self.style.setPlaceholderText("Describe the production direction: anthemic, dark, cinematic, punchy drums, sparse verse...")
        form.addRow("Generation engine", self.engine)
        form.addRow("Reference strength", self.reference)
        form.addRow("Vocal handling", self.vocal)
        form.addRow("Production direction", self.style)

    def sync(self):
        self.project.settings["engine"] = self.engine.currentText()
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

    def _complete(self, candidates, worker):
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


class ExportPage(QWidget):
    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent); self.project=project
        root=QVBoxLayout(self)
        title=QLabel("EXPORT CENTER"); title.setObjectName("PageTitle"); root.addWidget(title)
        song=QGroupBox("Song"); sl=QHBoxLayout(song)
        for label in ("Master WAV","MP3","FLAC","M4A","MP4 Video"):
            box=QCheckBox(label); box.setChecked(label in ("Master WAV","MP3")); sl.addWidget(box)
        root.addWidget(song)
        stems=QGroupBox("Stems"); st=QHBoxLayout(stems)
        for label in ("Vocal","Drums","Bass","Music","SFX","Instrumental"):
            box=QCheckBox(label); box.setChecked(True); st.addWidget(box)
        root.addWidget(stems)
        other=QGroupBox("Other"); ot=QHBoxLayout(other)
        for label in ("Lyrics LRC","Lyrics SRT","Project Archive","MIDI","Metadata"):
            box=QCheckBox(label); box.setChecked(label != "MIDI"); ot.addWidget(box)
        root.addWidget(other)
        self.location=QLineEdit(project.export_root); self.location.setPlaceholderText("Export folder")
        root.addWidget(self.location)
        root.addWidget(QPushButton("EXPORT ALL"),0,Qt.AlignLeft)
        root.addStretch(1)


class EnginesPage(QWidget):
    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent); self.project = project
        root = QVBoxLayout(self)
        title = QLabel("AI ENGINES"); title.setObjectName("PageTitle"); root.addWidget(title)
        info = QLabel("Configure generation providers. Drellion never silently switches to the Basic Test Engine.")
        info.setWordWrap(True); root.addWidget(info)

        ace = QGroupBox("ACE-Step 1.5 HTTP")
        form = QFormLayout(ace)
        self.ace_endpoint = QLineEdit(str(project.settings.get("ace_step_endpoint", "")))
        self.ace_endpoint.setPlaceholderText("http://127.0.0.1:8001 or your remote endpoint")
        self.ace_key = QLineEdit(str(project.settings.get("ace_step_api_key", "")))
        self.ace_key.setEchoMode(QLineEdit.Password)
        form.addRow("Endpoint", self.ace_endpoint); form.addRow("API key", self.ace_key)
        root.addWidget(ace)

        local = QGroupBox("Local Engines")
        lf = QFormLayout(local)
        self.ace_local = QLineEdit(str(project.settings.get("ace_step_local_command", "")))
        self.diff_local = QLineEdit(str(project.settings.get("diffrhythm_local_command", "")))
        lf.addRow("ACE-Step command", self.ace_local); lf.addRow("DiffRhythm command", self.diff_local)
        root.addWidget(local)

        self.status = QListWidget(); root.addWidget(self.status)
        row = QHBoxLayout()
        save = QPushButton("Save Engine Settings"); save.clicked.connect(self.sync)
        test = QPushButton("Refresh Status"); test.clicked.connect(self.refresh_status)
        row.addWidget(save); row.addWidget(test); row.addStretch(1); root.addLayout(row)
        root.addStretch(1)

    def sync(self):
        self.project.settings["ace_step_endpoint"] = self.ace_endpoint.text().strip()
        self.project.settings["ace_step_api_key"] = self.ace_key.text()
        self.project.settings["ace_step_local_command"] = self.ace_local.text().strip()
        self.project.settings["diffrhythm_local_command"] = self.diff_local.text().strip()
        self.project.touch()
        self.refresh_status()

    def refresh_status(self):
        self.status.clear()
        try:
            broker = create_broker(self.project)
            statuses = broker.statuses()
            if not statuses:
                self.status.addItem("No engines configured.")
            for item in statuses:
                self.status.addItem(f"{item.name}: {item.state.value.upper()} — {item.detail}")
        except Exception as exc:
            self.status.addItem(f"Engine status error: {exc}")


class HealthPage(QWidget):
    def __init__(self, project: ProjectState, parent=None):
        super().__init__(parent); self.project = project
        root = QVBoxLayout(self)
        title = QLabel("PROJECT HEALTH"); title.setObjectName("PageTitle"); root.addWidget(title)
        self.list = QListWidget(); root.addWidget(self.list)
        button = QPushButton("Run Project Check"); button.clicked.connect(self.refresh)
        root.addWidget(button, 0, Qt.AlignLeft); root.addStretch(1)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for item in check_project(self.project):
            prefix = "✓" if item.ok else "⚠"
            self.list.addItem(f"{prefix} {item.name}: {item.detail}")


class V2Workspace(QWidget):
    NAV = [
        ("Sources", 0), ("References", 1), ("Direction", 2), ("Previews", 3),
        ("Build", 4), ("Master", 5), ("Studio", 6), ("Library", 7),
        ("Export", 8), ("Versions", 9), ("Storage", 10), ("AI Engines", 11), ("Project Health", 12),
    ]

    def __init__(self, project: ProjectState, storage: StorageSettings, accessibility: AccessibilitySettings, parent=None):
        super().__init__(parent)
        self.project=project; self.storage=storage; self.accessibility=accessibility
        root=QVBoxLayout(self)
        header=QHBoxLayout()
        brand=QLabel("DRELLION NEXUS 2.0"); brand.setStyleSheet("font-size:20pt;font-weight:800;"); header.addWidget(brand)
        header.addStretch(1)
        self.project_label=QLabel(project.name); header.addWidget(self.project_label)
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
        self.sources=SourcesPage(project); self.references=ReferencesPage(project); self.direction=DirectionPage(project)
        self.stack.addWidget(self.sources)
        self.stack.addWidget(self.references)
        self.stack.addWidget(self.direction)
        self.previews = PreviewsPage(project); self.previews.play_requested.connect(self.play_audio); self.stack.addWidget(self.previews)
        self.build_page = BuildPage(project); self.build_page.play_requested.connect(self.play_audio); self.stack.addWidget(self.build_page)
        self.stack.addWidget(PlaceholderPage("6  MASTER", "Reference-aware mastering with loudness, true peak, tonal balance, width and volume-matched A/B.", ["Master Track"]))
        self.stack.addWidget(PlaceholderPage("STUDIO", "Timeline + browser + inspector + mixer + Ask Drellion command bar. Existing v1 Studio remains available while the v2 workspace is expanded."))
        self.stack.addWidget(PlaceholderPage("LIBRARY", "Soundbank, stems, SFX, MIDI, favourites, search, tags and user folders. Refresh detects new user-added sounds."))
        self.stack.addWidget(ExportPage(project))
        self.stack.addWidget(PlaceholderPage("VERSIONS", "Snapshots, autosaves, generated versions, A/B comparisons and restore points.", ["Create Snapshot"]))
        self.storage_page=StoragePage(storage); self.stack.addWidget(self.storage_page)
        self.engines_page=EnginesPage(project); self.stack.addWidget(self.engines_page)
        self.health_page=HealthPage(project); self.stack.addWidget(self.health_page)
        body.addWidget(self.stack,1)
        root.addLayout(body,1)
        self.player = PlayerBar(self)
        root.addWidget(self.player)
        self.goto(0)

    def goto(self,index:int):
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav_buttons): b.setChecked(i==index)

    def sync(self):
        self.sources.sync(); self.references.sync(); self.direction.sync(); self.storage_page.sync(); self.engines_page.sync()

    def play_audio(self, label: str, path: str):
        self.player.set_sources({label: path}, preferred=label)

    def open_accessibility(self):
        dialog=AccessibilityDialog(self.accessibility,self)
        dialog.exec()
