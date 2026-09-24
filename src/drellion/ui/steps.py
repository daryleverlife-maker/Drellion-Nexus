from __future__ import annotations

from pathlib import Path
import shutil
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QComboBox, QDoubleSpinBox, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

from ..exporter import PRESETS, export_audio
from ..library import SoundLibrary
from ..metadata import TrackMetadata, embed_metadata
from ..project import ReferenceSlot, SourceSlot
from ..storage import consolidate_file, ensure_project_folders
from ..youtube import youtube_oembed
from .export_center import ExportCenterDialog
from .reference_roles import ReferenceRolesDialog


AUDIO_FILTER = "Audio (*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.opus *.aiff *.aif *.wma)"
SOURCE_ROLES = ["Lead Vocal", "Backing Vocal", "Drums", "Bass", "Music", "Instrument", "Finished Song", "Other"]


class StepBase(QWidget):
    title = ""
    subtitle = ""

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 24)
        self.layout.setSpacing(12)

        heading = QLabel(self.title)
        heading.setStyleSheet("font-size:22pt;font-weight:700;")
        self.layout.addWidget(heading)

        subtitle = QLabel(self.subtitle)
        subtitle.setWordWrap(True)
        subtitle.setObjectName("Muted")
        self.layout.addWidget(subtitle)

    def card(self, title):
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setStyleSheet("font-size:13pt;font-weight:650;")
        layout.addWidget(heading)
        self.layout.addWidget(frame)
        return layout

    def busy(self, active: bool):
        if active:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents()


class SourceRow(QWidget):
    def __init__(self, step, index: int):
        super().__init__()
        self.step = step
        self.index = index
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)

        self.role = QComboBox()
        self.role.addItems(SOURCE_ROLES)
        self.role.setMinimumWidth(140)
        self.role.currentTextChanged.connect(self.changed)
        row.addWidget(self.role)

        self.path = QLineEdit()
        self.path.setPlaceholderText(f"Source {index + 1} — drop or choose audio")
        self.path.editingFinished.connect(self.changed)
        row.addWidget(self.path, 1)

        choose = QPushButton("Choose…")
        choose.clicked.connect(self.choose)
        row.addWidget(choose)

        self.preserve = QCheckBox("Preserve")
        self.preserve.toggled.connect(self.changed)
        row.addWidget(self.preserve)

        self.use = QCheckBox("Use")
        self.use.setChecked(True)
        self.use.toggled.connect(self.changed)
        row.addWidget(self.use)

        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        row.addWidget(clear)

    def slot(self) -> SourceSlot:
        return self.step.ensure_slot(self.index)

    def load(self):
        slot = self.slot()
        self.role.blockSignals(True)
        self.path.blockSignals(True)
        self.preserve.blockSignals(True)
        self.use.blockSignals(True)
        self.role.setCurrentText(slot.role if slot.role in SOURCE_ROLES else "Other")
        self.path.setText(slot.path)
        self.preserve.setChecked(slot.preserve)
        self.use.setChecked(slot.use_in_build)
        self.role.blockSignals(False)
        self.path.blockSignals(False)
        self.preserve.blockSignals(False)
        self.use.blockSignals(False)

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Source Audio", "", AUDIO_FILTER)
        if path:
            if bool(self.step.window.project.settings.get("consolidate_imports", True)):
                folders = ensure_project_folders(self.step.window.project, self.step.window.project_path)
                path = str(consolidate_file(path, folders.sources))
            self.path.setText(path)
            self.changed()
            if self.role.currentText() == "Lead Vocal":
                self.step.window.refresh_player_sources("Vocal")

    def clear(self):
        slot = self.slot()
        slot.path = ""
        slot.label = ""
        slot.preserve = False
        slot.use_in_build = True
        self.path.clear()
        self.preserve.setChecked(False)
        self.use.setChecked(True)
        self.changed()

    def changed(self, *_):
        slot = self.slot()
        slot.role = self.role.currentText()
        slot.path = self.path.text().strip()
        slot.label = Path(slot.path).name if slot.path else slot.role
        slot.preserve = self.preserve.isChecked()
        slot.use_in_build = self.use.isChecked()
        slot.enabled = bool(slot.path)
        if slot.role == "Lead Vocal" and slot.path:
            self.step.window.project.active_vocal_source_id = slot.id
        self.step.window.project.sync_legacy_slots()
        self.step.window.project.touch()
        self.step.window.refresh_summary()


class VocalLyricsStep(StepBase):
    title = "Sources & lyrics"
    subtitle = (
        "Add up to six source files here. Keep vocals, guitars or other stems locked with Preserve, "
        "and let Drellion rebuild only the parts you want changed."
    )

    def __init__(self, window):
        super().__init__(window)
        self.ensure_six()

        card = self.card("Your sources")
        self.rows = []
        for index in range(6):
            source_row = SourceRow(self, index)
            self.rows.append(source_row)
            card.addWidget(source_row)

        self.path = self.rows[0].path
        self.preserve = QComboBox()
        self.preserve.addItems(["Natural", "Polished", "Flexible"])
        self.preserve.setCurrentText(window.project.vocal_preservation)
        self.preserve.currentTextChanged.connect(self.change_preserve)
        card.addWidget(QLabel("Lead-vocal handling"))
        card.addWidget(self.preserve)

        lyrics_card = self.card("Lyrics")
        self.lyrics = QTextEdit()
        self.lyrics.setPlaceholderText(
            "Paste or type lyrics. v2 keeps these in the project and aligns them to the lead vocal."
        )
        self.lyrics.textChanged.connect(self.lyrics_changed)
        lyrics_card.addWidget(self.lyrics)

        next_button = QPushButton("Continue to References →")
        next_button.setObjectName("Primary")
        next_button.clicked.connect(lambda: self.window.goto_step(1))
        self.layout.addWidget(next_button, 0, Qt.AlignRight)
        self.layout.addStretch()
        self.refresh_from_project()

    def ensure_six(self):
        defaults = ["Lead Vocal", "Backing Vocal", "Drums", "Bass", "Music", "Other"]
        while len(self.window.project.sources) < 6:
            index = len(self.window.project.sources)
            self.window.project.sources.append(SourceSlot(
                role=defaults[index],
                preserve=index == 0,
                use_in_build=True,
            ))
        if not self.window.project.active_vocal_source_id:
            self.window.project.active_vocal_source_id = self.window.project.sources[0].id
        self.window.project.sync_legacy_slots()

    def ensure_slot(self, index: int) -> SourceSlot:
        self.ensure_six()
        return self.window.project.sources[index]

    def refresh_from_project(self):
        self.ensure_six()
        for row in self.rows:
            row.load()
        self.lyrics.blockSignals(True)
        self.lyrics.setPlainText(self.window.project.lyrics)
        self.lyrics.blockSignals(False)
        self.preserve.setCurrentText(self.window.project.vocal_preservation)

    def change_preserve(self, value):
        self.window.project.vocal_preservation = value
        self.window.snapshot("Changed vocal handling")

    def lyrics_changed(self):
        self.window.project.lyrics = self.lyrics.toPlainText()
        self.window.project.touch()
        self.window.refresh_summary()


class ReferenceRow(QWidget):
    def __init__(self, step, index: int):
        super().__init__()
        self.step = step
        self.index = index
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 8)

        top = QHBoxLayout()
        self.title = QLineEdit()
        self.title.setPlaceholderText(f"Reference {index + 1} title")
        self.title.editingFinished.connect(self.changed)
        top.addWidget(self.title, 2)
        self.artist = QLineEdit()
        self.artist.setPlaceholderText("Artist / channel")
        self.artist.editingFinished.connect(self.changed)
        top.addWidget(self.artist, 1)
        self.influence = QDoubleSpinBox()
        self.influence.setRange(0, 100)
        self.influence.setSuffix("%")
        self.influence.setDecimals(0)
        self.influence.valueChanged.connect(self.changed)
        top.addWidget(self.influence)
        self.enabled = QCheckBox("Use")
        self.enabled.toggled.connect(self.changed)
        top.addWidget(self.enabled)
        roles = QPushButton("Roles…")
        roles.clicked.connect(self.edit_roles)
        top.addWidget(roles)
        outer.addLayout(top)

        local = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setPlaceholderText("Local reference audio for deep analysis")
        self.path.editingFinished.connect(self.changed)
        local.addWidget(self.path, 1)
        choose = QPushButton("Audio…")
        choose.clicked.connect(self.choose)
        local.addWidget(choose)
        outer.addLayout(local)

        online = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("YouTube reference URL")
        self.url.editingFinished.connect(self.changed)
        online.addWidget(self.url, 1)
        metadata = QPushButton("Load title")
        metadata.clicked.connect(self.load_metadata)
        online.addWidget(metadata)
        open_button = QPushButton("Open YouTube")
        open_button.clicked.connect(self.open_youtube)
        online.addWidget(open_button)
        outer.addLayout(online)

        self.analysis = QLabel("Not analyzed")
        self.analysis.setObjectName("Muted")
        self.analysis.setWordWrap(True)
        outer.addWidget(self.analysis)

    def slot(self) -> ReferenceSlot:
        return self.step.ensure_slot(self.index)

    def load(self):
        slot = self.slot()
        for widget in (self.title, self.artist, self.path, self.url, self.influence, self.enabled):
            widget.blockSignals(True)
        self.title.setText(slot.title)
        self.artist.setText(slot.artist)
        self.path.setText(slot.path)
        self.url.setText(slot.youtube_url)
        self.influence.setValue(round(slot.influence * 100))
        self.enabled.setChecked(slot.enabled)
        for widget in (self.title, self.artist, self.path, self.url, self.influence, self.enabled):
            widget.blockSignals(False)
        if slot.analysis:
            self.analysis.setText(
                f"{slot.analysis.get('bpm', 0):.1f} BPM · "
                f"{slot.analysis.get('duration', 0):.1f}s · analyzed"
            )
        else:
            self.analysis.setText("Not analyzed")

    def changed(self, *_):
        slot = self.slot()
        slot.title = self.title.text().strip()
        slot.artist = self.artist.text().strip()
        slot.path = self.path.text().strip()
        slot.youtube_url = self.url.text().strip()
        slot.influence = self.influence.value() / 100.0
        slot.enabled = self.enabled.isChecked()
        if self.index == 0 and (slot.path or slot.youtube_url):
            self.step.window.project.active_reference_id = slot.id
        self.step.window.project.sync_legacy_slots()
        self.step.window.project.touch()
        self.step.window.refresh_summary()

    def edit_roles(self):
        slot = self.slot()
        if ReferenceRolesDialog(slot, self).exec():
            self.changed()
            self.step.window.snapshot(f"Changed Reference {self.index + 1} role influence")

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Reference Audio", "", AUDIO_FILTER)
        if path:
            if bool(self.step.window.project.settings.get("consolidate_imports", True)):
                folders = ensure_project_folders(self.step.window.project, self.step.window.project_path)
                path = str(consolidate_file(path, folders.references))
            self.path.setText(path)
            if not self.title.text().strip():
                self.title.setText(Path(path).stem)
            self.enabled.setChecked(True)
            self.changed()
            if self.index == 0:
                self.step.window.refresh_player_sources("Reference")

    def load_metadata(self):
        url = self.url.text().strip()
        if not url:
            return
        data = youtube_oembed(url)
        if data:
            self.title.setText(data.get("title", ""))
            self.artist.setText(data.get("artist", ""))
            self.enabled.setChecked(True)
            self.changed()
        else:
            QMessageBox.information(
                self,
                "YouTube Reference",
                "The URL is saved, but public title/channel metadata could not be loaded.",
            )

    def open_youtube(self):
        url = self.url.text().strip()
        if url:
            webbrowser.open(url)


class ReferenceStep(StepBase):
    title = "Reference Board"
    subtitle = (
        "Blend up to six songs. YouTube links identify and audition references; local audio enables "
        "deep BPM, energy, tone, stereo and dynamics analysis."
    )

    def __init__(self, window):
        super().__init__(window)
        self.ensure_six()
        card = self.card("References")
        self.rows = []
        for index in range(6):
            label = QLabel(f"REFERENCE {index + 1}")
            label.setStyleSheet("font-weight:650;")
            card.addWidget(label)
            row = ReferenceRow(self, index)
            self.rows.append(row)
            card.addWidget(row)

        self.path = self.rows[0].path

        analyze = QPushButton("ANALYZE ALL LOCAL REFERENCES")
        analyze.setObjectName("Primary")
        analyze.clicked.connect(self.analyze_all)
        self.layout.addWidget(analyze)

        next_button = QPushButton("Continue to Direction →")
        next_button.clicked.connect(lambda: self.window.goto_step(2))
        self.layout.addWidget(next_button, 0, Qt.AlignRight)
        self.layout.addStretch()
        self.refresh_from_project()

    def ensure_six(self):
        while len(self.window.project.references) < 6:
            index = len(self.window.project.references)
            self.window.project.references.append(ReferenceSlot(
                title="",
                influence=1.0 if index == 0 else 0.0,
                enabled=index == 0,
            ))
        if not self.window.project.active_reference_id:
            self.window.project.active_reference_id = self.window.project.references[0].id
        self.window.project.sync_legacy_slots()

    def ensure_slot(self, index: int) -> ReferenceSlot:
        self.ensure_six()
        return self.window.project.references[index]

    def refresh_from_project(self):
        self.ensure_six()
        for row in self.rows:
            row.load()

    def analyze_all(self):
        found = 0
        try:
            self.busy(True)
            for index, row in enumerate(self.rows):
                slot = self.ensure_slot(index)
                if not slot.enabled or not slot.path or not Path(slot.path).is_file():
                    continue
                analysis = self.window.engine.analyze_mix(slot.path)
                slot.analysis = {
                    "bpm": analysis.bpm,
                    "duration": analysis.duration,
                    "energy_curve": analysis.energy_curve,
                    "groove": analysis.groove,
                    "tone": analysis.tone,
                    "stereo": analysis.stereo,
                    "dynamics": analysis.dynamics,
                }
                row.analysis.setText(
                    f"{analysis.bpm:.1f} BPM · {analysis.duration:.1f}s · "
                    f"onset {analysis.groove.get('onset_density', 0.0):.2f}/s"
                )
                found += 1
            self.window.project.touch()
            self.window.snapshot("Analyzed reference board")
            QMessageBox.information(self, "Reference Board", f"Analyzed {found} local reference(s).")
        except Exception as exc:
            QMessageBox.critical(self, "Reference analysis failed", str(exc))
        finally:
            self.busy(False)


class SoundsStep(StepBase):
    title = "Direction & AI engine"
    subtitle = (
        "Choose the production engine explicitly. v2 never silently swaps a failed production model "
        "for the Basic Test Engine."
    )

    PROVIDERS = {
        "Automatic (production engines only)": "auto",
        "ACE-Step 1.5": "ace_step",
        "DiffRhythm 2": "diff_rhythm",
        "YuE": "yue",
        "Drellion Basic Test Engine": "basic_test",
    }

    def __init__(self, window):
        super().__init__(window)

        engine = self.card("AI engine")
        self.provider = QComboBox()
        self.provider.addItems(self.PROVIDERS.keys())
        current_id = str(window.project.settings.get("generation_provider", "auto"))
        for label, provider_id in self.PROVIDERS.items():
            if provider_id == current_id:
                self.provider.setCurrentText(label)
                break
        self.provider.currentTextChanged.connect(self.provider_changed)
        engine.addWidget(QLabel("Generation provider"))
        engine.addWidget(self.provider)

        self.ace_url = QLineEdit(str(window.project.settings.get("provider_ace_step_url", "http://127.0.0.1:8001")))
        self.ace_url.setPlaceholderText("ACE-Step endpoint, e.g. http://127.0.0.1:8001")
        self.ace_url.editingFinished.connect(self.endpoints_changed)
        engine.addWidget(QLabel("ACE-Step endpoint"))
        engine.addWidget(self.ace_url)

        self.diff_url = QLineEdit(str(window.project.settings.get("provider_diff_rhythm_url", "")))
        self.diff_url.setPlaceholderText("Optional DiffRhythm service endpoint")
        self.diff_url.editingFinished.connect(self.endpoints_changed)
        engine.addWidget(QLabel("DiffRhythm endpoint"))
        engine.addWidget(self.diff_url)

        self.yue_url = QLineEdit(str(window.project.settings.get("provider_yue_url", "")))
        self.yue_url.setPlaceholderText("Optional YuE service endpoint")
        self.yue_url.editingFinished.connect(self.endpoints_changed)
        engine.addWidget(QLabel("YuE endpoint"))
        engine.addWidget(self.yue_url)

        self.basic = QCheckBox("Enable Basic Test Engine (developer/demo quality only)")
        self.basic.setChecked(bool(window.project.settings.get("enable_basic_test_engine", False)))
        self.basic.toggled.connect(self.endpoints_changed)
        engine.addWidget(self.basic)

        status = QPushButton("Refresh engine status")
        status.clicked.connect(self.refresh_provider_status)
        engine.addWidget(status)
        self.provider_status = QLabel("Not checked.")
        self.provider_status.setWordWrap(True)
        self.provider_status.setObjectName("Muted")
        engine.addWidget(self.provider_status)

        direction = self.card("Production direction")
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText(
            "Example: anthemic cinematic hip-hop, heavy controlled drums and bass, sparse verses, "
            "large chorus lift, dramatic transitions, leave space for the vocal"
        )
        self.prompt.setPlainText(str(window.project.settings.get("production_direction_prompt", "")))
        self.prompt.textChanged.connect(self.direction_changed)
        direction.addWidget(self.prompt)

        self.reference_strength = QDoubleSpinBox()
        self.reference_strength.setRange(0, 100)
        self.reference_strength.setSuffix("%")
        self.reference_strength.setValue(float(window.project.settings.get("reference_audio_strength", 25.0)))
        self.reference_strength.valueChanged.connect(self.direction_changed)
        direction.addWidget(QLabel("Reference-audio strength"))
        direction.addWidget(self.reference_strength)

        guard = QComboBox()
        guard.addItems(["Standard", "High", "Maximum"])
        guard.setCurrentText(window.project.originality_protection)
        guard.currentTextChanged.connect(self.set_guard)
        direction.addWidget(QLabel("Originality protection"))
        direction.addWidget(guard)

        sounds = self.card("Sound library")
        row = QHBoxLayout()
        self.path = QLineEdit(window.project.sound_library_path)
        self.path.setPlaceholderText("Drellion sound library")
        row.addWidget(self.path, 1)
        choose = QPushButton("Choose…")
        choose.clicked.connect(self.choose_library)
        row.addWidget(choose)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        sounds.addLayout(row)
        self.sound_status = QLabel("Not indexed.")
        self.sound_status.setObjectName("Muted")
        sounds.addWidget(self.sound_status)

        next_button = QPushButton("Continue to Previews →")
        next_button.setObjectName("Primary")
        next_button.clicked.connect(lambda: self.window.goto_step(3))
        self.layout.addWidget(next_button, 0, Qt.AlignRight)
        self.layout.addStretch()

    def provider_changed(self):
        self.window.project.settings["generation_provider"] = self.PROVIDERS[self.provider.currentText()]
        self.window.snapshot("Changed generation provider")

    def endpoints_changed(self, *_):
        self.window.project.settings["provider_ace_step_url"] = self.ace_url.text().strip()
        self.window.project.settings["provider_diff_rhythm_url"] = self.diff_url.text().strip()
        self.window.project.settings["provider_yue_url"] = self.yue_url.text().strip()
        self.window.project.settings["enable_basic_test_engine"] = self.basic.isChecked()
        self.window.project.touch()

    def direction_changed(self, *_):
        self.window.project.settings["production_direction_prompt"] = self.prompt.toPlainText().strip()
        self.window.project.settings["reference_audio_strength"] = self.reference_strength.value()
        self.window.project.touch()

    def set_guard(self, value):
        self.window.project.originality_protection = value
        self.window.snapshot("Changed originality protection")

    def refresh_provider_status(self):
        self.endpoints_changed()
        try:
            statuses = self.window.engine.provider_statuses(self.window.project)
            self.provider_status.setText("\n".join(
                f"{item.name}: {item.state.value} — {item.detail}" for item in statuses
            ))
        except Exception as exc:
            self.provider_status.setText(str(exc))

    def choose_library(self):
        path = QFileDialog.getExistingDirectory(self, "Choose Sound Library")
        if path:
            self.path.setText(path)
            self.window.project.sound_library_path = path
            self.window.project.storage.sound_library_root = path
            self.window.snapshot("Changed sound library")
            self.refresh()

    def refresh(self):
        root = self.path.text().strip()
        if not root:
            self.sound_status.setText("Choose a sound library folder.")
            return
        try:
            self.busy(True)
            library = SoundLibrary(root)
            items = library.scan()
            self.window.project.sound_library_path = root
            self.window.project.settings["sound_count"] = len(items)
            self.sound_status.setText(f"{len(items):,} unique sounds indexed.")
            self.window.snapshot("Refreshed sound library")
        except Exception as exc:
            QMessageBox.critical(self, "Sound Library", str(exc))
        finally:
            self.busy(False)


class PreviewStep(StepBase):
    title = "Three production previews"
    subtitle = (
        "Drellion asks the selected production engine for three different vocal-conditioned arrangements. "
        "Every candidate must pass Beat QC before it is shown."
    )

    def __init__(self, window):
        super().__init__(window)
        self.preview_paths: dict[str, str] = {}
        self.preview_descriptions: dict[str, QLabel] = {}

        card = self.card("Arrangement previews")
        generate = QPushButton("GENERATE 3 REAL PREVIEWS")
        generate.setObjectName("Primary")
        generate.clicked.connect(self.generate)
        card.addWidget(generate)

        for name in ("Preview A", "Preview B", "Preview C"):
            row = QHBoxLayout()
            name_label = QLabel(name)
            name_label.setStyleSheet("font-weight:650;")
            row.addWidget(name_label)
            description = QLabel("Not generated")
            description.setObjectName("Muted")
            description.setWordWrap(True)
            row.addWidget(description, 1)
            self.preview_descriptions[name] = description

            play = QPushButton("Play")
            play.clicked.connect(lambda _=False, n=name: self.play(n))
            row.addWidget(play)
            select = QPushButton("Select")
            select.clicked.connect(lambda _=False, n=name: self.select(n))
            row.addWidget(select)
            card.addLayout(row)

        sfx_card = self.card("Smart SFX")
        intro = QLabel(
            "Optional lyric-aware effects are added only after the musical arrangement works."
        )
        intro.setWordWrap(True)
        sfx_card.addWidget(intro)
        controls = QHBoxLayout()
        suggest = QPushButton("Suggest SFX")
        suggest.clicked.connect(self.suggest_fx)
        controls.addWidget(suggest)
        clear = QPushButton("Clear SFX")
        clear.clicked.connect(self.clear_selected_fx)
        controls.addWidget(clear)
        controls.addStretch()
        sfx_card.addLayout(controls)
        self.sfx_status = QLabel("No SFX selected.")
        self.sfx_status.setObjectName("Muted")
        sfx_card.addWidget(self.sfx_status)
        self.sfx_rows_widget = QWidget()
        self.sfx_rows = QVBoxLayout(self.sfx_rows_widget)
        self.sfx_rows.setContentsMargins(0, 0, 0, 0)
        sfx_card.addWidget(self.sfx_rows_widget)

        next_button = QPushButton("Continue to Build →")
        next_button.clicked.connect(lambda: self.window.goto_step(4))
        self.layout.addWidget(next_button, 0, Qt.AlignRight)
        self.layout.addStretch()

    def _clear_sfx_rows(self):
        while self.sfx_rows.count():
            item = self.sfx_rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _update_sfx_status(self):
        selected = list(self.window.project.settings.get("selected_sfx", []) or [])
        self.sfx_status.setText(f"{len(selected)} SFX event(s) selected." if selected else "No SFX selected.")

    def suggest_fx(self):
        try:
            self.busy(True)
            suggestions = self.window.engine.smart_sfx(self.window.project)
            self._clear_sfx_rows()
            for suggestion in suggestions:
                wrapper = QWidget()
                row = QHBoxLayout(wrapper)
                row.setContentsMargins(0, 0, 0, 0)
                label = QLabel(f"{suggestion.time:6.1f}s · {suggestion.lyric} · {suggestion.reason}")
                label.setWordWrap(True)
                row.addWidget(label, 1)
                choice = QComboBox()
                for option in suggestion.options:
                    choice.addItem(Path(option).name, option)
                row.addWidget(choice)
                use = QPushButton("Use")
                use.clicked.connect(lambda _=False, s=suggestion, combo=choice: self.use_fx(s, combo))
                row.addWidget(use)
                self.sfx_rows.addWidget(wrapper)
            if not suggestions:
                self.sfx_rows.addWidget(QLabel("No suitable SFX suggestions found."))
            self._update_sfx_status()
        except Exception as exc:
            QMessageBox.critical(self, "Smart SFX failed", str(exc))
        finally:
            self.busy(False)

    def use_fx(self, suggestion, combo):
        path = combo.currentData()
        if not path:
            return
        selected = list(self.window.project.settings.get("selected_sfx", []) or [])
        selected = [event for event in selected if abs(float(event.get("time", -999)) - suggestion.time) > 0.02]
        selected.append({
            "time": float(suggestion.time),
            "path": str(path),
            "gain_db": -10.0,
            "lyric": suggestion.lyric,
            "reason": suggestion.reason,
        })
        selected.sort(key=lambda event: float(event["time"]))
        self.window.project.settings["selected_sfx"] = selected
        self.window.snapshot("Selected Smart SFX")
        self._update_sfx_status()

    def clear_selected_fx(self):
        self.window.project.settings["selected_sfx"] = []
        self.window.snapshot("Cleared Smart SFX")
        self._update_sfx_status()

    def generate(self):
        try:
            self.busy(True)
            output = self.window.project_output_dir() / "Previews"
            previews = self.window.engine.generate_previews(self.window.project, output)
            self.preview_paths = {item.name: item.audio_path for item in previews}
            self.window.project.settings["preview_paths"] = dict(self.preview_paths)
            for item in previews:
                self.preview_descriptions[item.name].setText(item.description)
            self.window.snapshot("Generated production previews")
            self.window.refresh_player_sources("Preview A")
            QMessageBox.information(
                self,
                "Previews ready",
                "Three production-quality candidates passed Beat QC. Listen to each before Build.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Preview generation failed", str(exc))
        finally:
            self.busy(False)

    def play(self, name):
        path = self.preview_paths.get(name, "")
        if not path:
            QMessageBox.information(self, name, "Generate previews first.")
            return
        self.window.player.load_path(path, name)
        self.window.player.player.play()

    def select(self, name):
        if name not in self.preview_paths:
            QMessageBox.information(self, name, "Generate previews first.")
            return
        self.window.project.selected_preview = name
        self.window.project.settings["selected_preview_path"] = self.preview_paths[name]
        self.window.snapshot("Selected " + name)
        self.window.refresh_player_sources(name)


class BuildStep(StepBase):
    title = "Build the full song"
    subtitle = (
        "The full build uses the same production provider and direction that produced the selected preview. "
        "A failed quality gate stops here instead of sending bad audio to Master."
    )

    def __init__(self, window):
        super().__init__(window)
        card = self.card("Build pipeline")
        card.addWidget(QLabel("Sources → Reference Blend → AI Engine → Beat QC → Build → Studio"))
        self.status = QLabel("Select a preview first.")
        self.status.setObjectName("Muted")
        card.addWidget(self.status)
        button = QPushButton("BUILD FULL SONG")
        button.setObjectName("Primary")
        button.clicked.connect(self.build_song)
        card.addWidget(button)

        next_button = QPushButton("Continue to Master →")
        next_button.clicked.connect(lambda: self.window.goto_step(5))
        self.layout.addWidget(next_button, 0, Qt.AlignRight)
        self.layout.addStretch()

    def build_song(self):
        if not self.window.project.selected_preview:
            QMessageBox.information(self, "Build", "Select Preview A, B or C first.")
            return
        try:
            self.busy(True)
            self.status.setText("Generating full vocal-conditioned production…")
            QApplication.processEvents()
            result = self.window.engine.build(
                self.window.project,
                self.window.project_output_dir() / "Build",
            )
            self.window.project.build_path = result.build_path
            self.window.project.settings["generated_instrumental"] = result.instrumental_path
            self.window.project.settings["build_report"] = result.report_path
            self.window.project.settings["lyrics_lrc"] = result.lyric_path
            self.window.snapshot("Built full song")
            self.window.refresh_player_sources("Build")
            self.status.setText("Build complete and Beat QC passed.")
            QMessageBox.information(self, "Build complete", result.build_path)
        except Exception as exc:
            self.status.setText("Build stopped.")
            QMessageBox.critical(self, "Build stopped", str(exc))
        finally:
            self.busy(False)


class MasterStep(StepBase):
    title = "Master & deliver"
    subtitle = (
        "Master only after the arrangement works. Export the master, premaster, vocal and Studio stems "
        "from the dedicated Export Center."
    )

    def __init__(self, window):
        super().__init__(window)
        card = self.card("Master")
        self.target = QComboBox()
        self.target.addItems(["-14 LUFS", "-12 LUFS", "-10 LUFS", "-9 LUFS"])
        card.addWidget(QLabel("Delivery loudness"))
        card.addWidget(self.target)
        master = QPushButton("MASTER TRACK")
        master.setObjectName("Primary")
        master.clicked.connect(self.master_track)
        card.addWidget(master)

        delivery = self.card("Delivery")
        export_center = QPushButton("OPEN EXPORT CENTER")
        export_center.setObjectName("Primary")
        export_center.clicked.connect(self.open_export_center)
        delivery.addWidget(export_center)
        folder = QPushButton("Open project/export folder")
        folder.clicked.connect(self.open_folder)
        delivery.addWidget(folder)
        self.layout.addStretch()

    def master_track(self):
        try:
            self.busy(True)
            self.window.project.settings["target_lufs"] = float(self.target.currentText().split()[0])
            master_path = self.window.engine.master(
                self.window.project,
                self.window.project_output_dir() / "Master",
            )
            self.window.project.master_path = master_path
            self.window.snapshot("Mastered track")
            self.window.refresh_player_sources("Master")
            QMessageBox.information(self, "Master complete", master_path)
        except Exception as exc:
            QMessageBox.critical(self, "Master failed", str(exc))
        finally:
            self.busy(False)

    def open_export_center(self):
        ExportCenterDialog(self.window, self).exec()

    def open_folder(self):
        path = self.window.project_output_dir().parent
        webbrowser.open(path.as_uri())
