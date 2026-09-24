from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QScrollArea, QSlider, QSpinBox, QStackedWidget, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget
)

from ..accessibility import AccessibilitySettings
from ..project import ProjectState, SourceAsset, ReferenceAsset
from ..storage import StorageSettings


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


class V2Workspace(QWidget):
    NAV = [
        ("Sources", 0), ("References", 1), ("Direction", 2), ("Previews", 3),
        ("Build", 4), ("Master", 5), ("Studio", 6), ("Library", 7),
        ("Export", 8), ("Versions", 9), ("Storage", 10),
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
        self.stack.addWidget(PlaceholderPage("4  PREVIEWS", "Generate three real 20–30 second arrangements, run automatic quality checks, then audition Vocal / Instrumental / Together / Reference A-B.", ["Generate 3 Previews", "Regenerate Failed"]))
        self.stack.addWidget(PlaceholderPage("5  BUILD", "Build the chosen arrangement into editable stems. The selected provider must be ready; Drellion will not silently switch to the Basic Test Engine.", ["Build Full Song"]))
        self.stack.addWidget(PlaceholderPage("6  MASTER", "Reference-aware mastering with loudness, true peak, tonal balance, width and volume-matched A/B.", ["Master Track"]))
        self.stack.addWidget(PlaceholderPage("STUDIO", "Timeline + browser + inspector + mixer + Ask Drellion command bar. Existing v1 Studio remains available while the v2 workspace is expanded."))
        self.stack.addWidget(PlaceholderPage("LIBRARY", "Soundbank, stems, SFX, MIDI, favourites, search, tags and user folders. Refresh detects new user-added sounds."))
        self.stack.addWidget(ExportPage(project))
        self.stack.addWidget(PlaceholderPage("VERSIONS", "Snapshots, autosaves, generated versions, A/B comparisons and restore points.", ["Create Snapshot"]))
        self.storage_page=StoragePage(storage); self.stack.addWidget(self.storage_page)
        body.addWidget(self.stack,1)
        root.addLayout(body,1)
        self.goto(0)

    def goto(self,index:int):
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav_buttons): b.setChecked(i==index)

    def sync(self):
        self.sources.sync(); self.references.sync(); self.direction.sync(); self.storage_page.sync()

    def open_accessibility(self):
        dialog=AccessibilityDialog(self.accessibility,self)
        dialog.exec()
