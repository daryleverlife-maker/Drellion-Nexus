from __future__ import annotations

from pathlib import Path
import shutil

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QTextEdit,
    QVBoxLayout, QWidget,
)

from ..exporter import PRESETS, export_audio
from ..library import SoundLibrary
from ..metadata import TrackMetadata, embed_metadata


AUDIO_FILTER = "Audio (*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.opus *.aiff *.aif *.wma)"


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
        heading.setStyleSheet("font-size:22pt;font-weight:650;")
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
        heading.setStyleSheet("font-size:13pt;font-weight:600;")
        layout.addWidget(heading)
        self.layout.addWidget(frame)
        return layout

    def busy(self, active: bool):
        QApplication.setOverrideCursor(Qt.WaitCursor) if active else QApplication.restoreOverrideCursor()
        QApplication.processEvents()


class VocalLyricsStep(StepBase):
    title = "Start with the voice"
    subtitle = "Your vocal controls melody, timing and phrasing. A completed song is optional."

    def __init__(self, window):
        super().__init__(window)

        card = self.card("Vocal stem")
        row = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setPlaceholderText("Drop or choose a vocal stem")
        row.addWidget(self.path, 1)
        button = QPushButton("Choose…")
        button.clicked.connect(self.choose)
        row.addWidget(button)
        card.addLayout(row)

        self.preserve = QComboBox()
        self.preserve.addItems(["Natural", "Polished", "Flexible"])
        self.preserve.setCurrentText(window.project.vocal_preservation)
        self.preserve.currentTextChanged.connect(self.change_preserve)
        card.addWidget(QLabel("Vocal preservation"))
        card.addWidget(self.preserve)

        lyrics_card = self.card("Lyrics")
        self.lyrics = QTextEdit()
        self.lyrics.setPlaceholderText(
            "Paste or type lyrics here. Drellion will align them to the vocal."
        )
        self.lyrics.textChanged.connect(self.lyrics_changed)
        lyrics_card.addWidget(self.lyrics)

        next_button = QPushButton("Continue to Reference →")
        next_button.setObjectName("Primary")
        next_button.clicked.connect(lambda: self.window.goto_step(1))
        self.layout.addWidget(next_button, 0, Qt.AlignRight)
        self.layout.addStretch()

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Vocal", "", AUDIO_FILTER)
        if path:
            self.path.setText(path)
            self.window.project.vocal.path = path
            self.window.project.vocal.label = Path(path).name
            self.window.snapshot("Loaded vocal")
            self.window.refresh_player_sources("Vocal")

    def change_preserve(self, value):
        self.window.project.vocal_preservation = value
        self.window.snapshot("Changed vocal preservation")

    def lyrics_changed(self):
        self.window.project.lyrics = self.lyrics.toPlainText()
        self.window.project.touch()
        self.window.refresh_summary()


class ReferenceStep(StepBase):
    title = "Choose the production direction"
    subtitle = (
        "The reference guides groove, energy, structure, tone and mix character. "
        "Its recording is never copied into the output."
    )

    def __init__(self, window):
        super().__init__(window)

        card = self.card("Reference audio")
        row = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setPlaceholderText("Choose a reference song")
        row.addWidget(self.path, 1)
        button = QPushButton("Choose…")
        button.clicked.connect(self.choose)
        row.addWidget(button)
        card.addLayout(row)

        self.analysis = QLabel("Not analyzed yet.")
        self.analysis.setWordWrap(True)
        self.analysis.setObjectName("Muted")
        card.addWidget(self.analysis)

        analyze = QPushButton("Analyze Reference")
        analyze.clicked.connect(self.analyze)
        card.addWidget(analyze)

        influence = QComboBox()
        influence.addItems(["Light", "Balanced", "Strong"])
        influence.setCurrentText(window.project.reference_influence)
        influence.currentTextChanged.connect(self.set_influence)
        card.addWidget(QLabel("Reference influence"))
        card.addWidget(influence)

        guard = QComboBox()
        guard.addItems(["Standard", "High", "Maximum"])
        guard.setCurrentText(window.project.originality_protection)
        guard.currentTextChanged.connect(self.set_guard)
        card.addWidget(QLabel("Originality protection"))
        card.addWidget(guard)

        next_button = QPushButton("Continue to Sounds →")
        next_button.setObjectName("Primary")
        next_button.clicked.connect(lambda: self.window.goto_step(2))
        self.layout.addWidget(next_button, 0, Qt.AlignRight)
        self.layout.addStretch()

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Reference", "", AUDIO_FILTER)
        if path:
            self.path.setText(path)
            self.window.project.reference.path = path
            self.window.project.reference.label = Path(path).name
            self.window.snapshot("Loaded reference")
            self.window.refresh_player_sources("Reference")

    def analyze(self):
        try:
            self.busy(True)
            result = self.window.engine.analyze_reference(self.window.project)
            energy = ", ".join(f"{x:.2f}" for x in result.energy_curve[:6])
            self.analysis.setText(
                f"Duration: {result.duration:.1f}s\n"
                f"Estimated BPM: {result.bpm:.1f}\n"
                f"Onset density: {result.groove.get('onset_density', 0.0):.2f}/s\n"
                f"Energy shape: {energy}{'…' if len(result.energy_curve) > 6 else ''}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Reference analysis failed", str(exc))
        finally:
            self.busy(False)

    def set_influence(self, value):
        self.window.project.reference_influence = value
        self.window.snapshot("Changed reference influence")

    def set_guard(self, value):
        self.window.project.originality_protection = value
        self.window.snapshot("Changed originality protection")


class SoundsStep(StepBase):
    title = "Pick the sound palette"
    subtitle = (
        "Use the Drellion library or point Nexus at another folder. "
        "User-added sounds remain refreshable."
    )

    def __init__(self, window):
        super().__init__(window)

        card = self.card("Sound library")
        row = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setPlaceholderText("Default Drellion library")
        row.addWidget(self.path, 1)

        choose = QPushButton("Choose folder…")
        choose.clicked.connect(self.choose)
        row.addWidget(choose)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        card.addLayout(row)

        self.status = QLabel("Choose a folder to index sounds.")
        self.status.setObjectName("Muted")
        card.addWidget(self.status)

        self.list = QListWidget()
        card.addWidget(self.list)

        next_button = QPushButton("Continue to Preview →")
        next_button.setObjectName("Primary")
        next_button.clicked.connect(lambda: self.window.goto_step(3))
        self.layout.addWidget(next_button, 0, Qt.AlignRight)
        self.layout.addStretch()

    def choose(self):
        path = QFileDialog.getExistingDirectory(self, "Choose Sound Library")
        if path:
            self.path.setText(path)
            self.window.project.sound_library_path = path
            self.window.snapshot("Changed sound library")
            self.refresh()

    def refresh(self):
        root = self.path.text().strip() or self.window.project.sound_library_path
        if not root:
            QMessageBox.information(self, "Sound Library", "Choose a sound-library folder first.")
            return
        try:
            self.busy(True)
            library = SoundLibrary(root)
            items = library.scan()
            self.list.clear()
            for item in items[:2000]:
                self.list.addItem(f"{item.name}  [{item.extension[1:].upper()}]")
            if len(items) > 2000:
                self.list.addItem(f"… plus {len(items) - 2000:,} more")
            self.status.setText(f"{len(items):,} unique audio files indexed.")
            self.window.project.sound_library_path = root
            self.window.project.settings["sound_count"] = len(items)
            self.window.snapshot("Refreshed sound library")
        except Exception as exc:
            QMessageBox.critical(self, "Sound Library", str(exc))
        finally:
            self.busy(False)


class PreviewStep(StepBase):
    title = "Hear the arrangement before building"
    subtitle = (
        "Generate three different vocal-matched arrangements and choose one "
        "before committing to the full song."
    )

    def __init__(self, window):
        super().__init__(window)
        self.preview_paths: dict[str, str] = {}
        self.preview_descriptions: dict[str, QLabel] = {}

        card = self.card("Arrangement previews")
        generate = QPushButton("GENERATE 3 PREVIEWS")
        generate.setObjectName("Primary")
        generate.clicked.connect(self.generate)
        card.addWidget(generate)

        for name in ("Preview A", "Preview B", "Preview C"):
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
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
        sfx_intro = QLabel(
            "Drellion uses lyric timing and the active sound library to suggest "
            "three effect choices for suitable moments."
        )
        sfx_intro.setWordWrap(True)
        sfx_card.addWidget(sfx_intro)

        sfx_controls = QHBoxLayout()
        suggest_button = QPushButton("Suggest SFX")
        suggest_button.clicked.connect(self.suggest_fx)
        sfx_controls.addWidget(suggest_button)
        clear_button = QPushButton("Clear selected SFX")
        clear_button.clicked.connect(self.clear_selected_fx)
        sfx_controls.addWidget(clear_button)
        sfx_controls.addStretch()
        sfx_card.addLayout(sfx_controls)

        self.sfx_status = QLabel("No SFX selected.")
        self.sfx_status.setObjectName("Muted")
        sfx_card.addWidget(self.sfx_status)

        self.sfx_rows_widget = QWidget()
        self.sfx_rows = QVBoxLayout(self.sfx_rows_widget)
        self.sfx_rows.setContentsMargins(0, 0, 0, 0)
        sfx_card.addWidget(self.sfx_rows_widget)

        next_button = QPushButton("Continue to Build →")
        next_button.setObjectName("Primary")
        next_button.clicked.connect(lambda: self.window.goto_step(4))
        self.layout.addWidget(next_button, 0, Qt.AlignRight)
        self.layout.addStretch()

    def _clear_sfx_rows(self):
        while self.sfx_rows.count():
            item = self.sfx_rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            child_layout = item.layout()
            if child_layout is not None:
                while child_layout.count():
                    child = child_layout.takeAt(0)
                    if child.widget() is not None:
                        child.widget().deleteLater()

    def _update_sfx_status(self):
        selected = list(self.window.project.settings.get("selected_sfx", []) or [])
        self.sfx_status.setText(
            f"{len(selected)} SFX event{'s' if len(selected) != 1 else ''} selected for Build."
            if selected else "No SFX selected."
        )

    def suggest_fx(self):
        try:
            self.busy(True)
            suggestions = self.window.engine.smart_sfx(self.window.project)
            self._clear_sfx_rows()
            if not suggestions:
                self.sfx_rows.addWidget(
                    QLabel("No matching SFX found. Add lyrics and refresh a sound library with FX files.")
                )
                return

            for suggestion in suggestions:
                row_widget = QWidget()
                row = QHBoxLayout(row_widget)
                row.setContentsMargins(0, 0, 0, 0)

                label = QLabel(
                    f"{suggestion.time:6.1f}s  ·  {suggestion.lyric}  ·  {suggestion.reason}"
                )
                label.setWordWrap(True)
                row.addWidget(label, 1)

                choice = QComboBox()
                for option in suggestion.options:
                    choice.addItem(Path(option).name, option)
                choice.setMinimumWidth(250)
                row.addWidget(choice)

                use = QPushButton("Use")
                use.clicked.connect(
                    lambda _=False, s=suggestion, combo=choice: self.use_fx(s, combo)
                )
                row.addWidget(use)
                self.sfx_rows.addWidget(row_widget)

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
        selected = [
            event for event in selected
            if abs(float(event.get("time", -999.0)) - float(suggestion.time)) > 0.02
        ]
        selected.append({
            "time": float(suggestion.time),
            "path": str(path),
            "gain_db": -10.0,
            "lyric": suggestion.lyric,
            "reason": suggestion.reason,
        })
        selected.sort(key=lambda event: float(event.get("time", 0.0)))
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
            for item in previews:
                self.preview_descriptions[item.name].setText(item.description)
            self.window.snapshot("Generated arrangement previews")
            self.window.refresh_player_sources("Preview A")
            QMessageBox.information(
                self,
                "Previews ready",
                "Three new arrangements were rendered under your vocal. "
                "Listen to each one, then select the direction you want.",
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
        self.window.snapshot("Selected " + name)
        self.window.refresh_player_sources(name)


class BuildStep(StepBase):
    title = "Build the song"
    subtitle = "Create the full original instrumental around your vocal and selected preview."

    def __init__(self, window):
        super().__init__(window)
        card = self.card("Build pipeline")
        card.addWidget(
            QLabel("Vocal → Drums → Bass → Harmony → Arrangement → SFX → Premix")
        )
        self.status = QLabel("Ready when Vocal, Reference and a Preview direction are set.")
        self.status.setObjectName("Muted")
        card.addWidget(self.status)

        button = QPushButton("BUILD SONG")
        button.setObjectName("Primary")
        button.clicked.connect(self.build_song)
        card.addWidget(button)

        next_button = QPushButton("Continue to Master →")
        next_button.clicked.connect(lambda: self.window.goto_step(5))
        self.layout.addWidget(next_button, 0, Qt.AlignRight)
        self.layout.addStretch()

    def build_song(self):
        try:
            self.busy(True)
            self.status.setText("Building new instrumental and mixing preserved vocal…")
            QApplication.processEvents()
            result = self.window.engine.build(
                self.window.project,
                self.window.project_output_dir() / "Build",
            )
            self.window.project.build_path = result.build_path
            self.window.project.settings["generated_instrumental"] = result.instrumental_path
            self.window.project.settings["build_report"] = result.report_path
            self.window.project.settings["lyrics_lrc"] = result.lyric_path
            self.window.snapshot("Built song")
            self.window.refresh_player_sources("Build")
            self.status.setText("Build complete.")
            QMessageBox.information(
                self,
                "Build complete",
                f"Song: {result.build_path}\n\nInstrumental: {result.instrumental_path}",
            )
        except Exception as exc:
            self.status.setText("Build failed.")
            QMessageBox.critical(self, "Build failed", str(exc))
        finally:
            self.busy(False)


class MasterStep(StepBase):
    title = "Master and export"
    subtitle = (
        "Finish the mix after the music works. Mastering is final polish, "
        "not the arrangement engine."
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

        export_card = self.card("Export")
        self.format = QComboBox()
        self.format.addItems(PRESETS.keys())
        export_card.addWidget(QLabel("Format"))
        export_card.addWidget(self.format)

        self.meta_title = QLineEdit()
        self.meta_title.setPlaceholderText("Song title")
        self.meta_title.setText(window.project.name if window.project.name != "Untitled" else "")
        self.meta_artist = QLineEdit()
        self.meta_artist.setPlaceholderText("Artist")
        self.meta_album = QLineEdit()
        self.meta_album.setPlaceholderText("Album (optional)")
        self.embed_lyrics = QCheckBox("Embed project lyrics when supported")
        self.embed_lyrics.setChecked(True)
        export_card.addWidget(self.meta_title)
        export_card.addWidget(self.meta_artist)
        export_card.addWidget(self.meta_album)
        export_card.addWidget(self.embed_lyrics)

        export_button = QPushButton("Export…")
        export_button.clicked.connect(self.export)
        export_card.addWidget(export_button)

        self.layout.addStretch()

    def master_track(self):
        try:
            self.busy(True)
            self.window.project.settings["target_lufs"] = float(
                self.target.currentText().split()[0]
            )
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

    def export(self):
        source = self.window.project.master_path or self.window.project.build_path
        if not source:
            QMessageBox.information(self, "Export", "Build or master the song first.")
            return

        preset = PRESETS[self.format.currentText()]
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Export Track",
            str(Path(source).with_suffix(preset.extension)),
            f"{preset.name} (*{preset.extension})",
        )
        if not target:
            return
        try:
            self.busy(True)
            output = export_audio(source, target, self.format.currentText())
            lyrics = self.window.project.lyrics if self.embed_lyrics.isChecked() else ""
            metadata = TrackMetadata(
                title=self.meta_title.text().strip(),
                artist=self.meta_artist.text().strip(),
                album=self.meta_album.text().strip(),
                lyrics=lyrics,
            )
            warnings = embed_metadata(output, metadata)

            lrc_source = self.window.project.settings.get("lyrics_lrc", "")
            if self.embed_lyrics.isChecked() and lrc_source and Path(lrc_source).is_file():
                shutil.copy2(lrc_source, Path(output).with_suffix(".lrc"))

            self.window.project.settings["export_metadata"] = {
                "title": metadata.title,
                "artist": metadata.artist,
                "album": metadata.album,
                "embed_lyrics": self.embed_lyrics.isChecked(),
            }
            self.window.snapshot("Exported track")

            message = str(output)
            if warnings:
                message += "\n\n" + "\n".join(warnings)
            QMessageBox.information(self, "Export complete", message)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
        finally:
            self.busy(False)
