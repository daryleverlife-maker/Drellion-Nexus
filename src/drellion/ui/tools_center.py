from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QVBoxLayout,
)

from ..storage import ensure_project_folders
from ..tools import audio_to_midi, clean_vocal_deepfilter, separate_open_unmix, tool_statuses
from ..transcription import transcribe_faster_whisper, words_to_lrc


class ToolsCenterDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent or main)
        self.main = main
        self.project = main.project
        self.setWindowTitle("Drellion Nexus — AI & Audio Tools")
        self.resize(760, 720)

        outer = QVBoxLayout(self)
        title = QLabel("AI & AUDIO TOOLS")
        title.setStyleSheet("font-size:18pt;font-weight:700;")
        outer.addWidget(title)
        note = QLabel(
            "Optional open-source tools are discovered on your system. Drellion keeps them modular "
            "so the core app stays usable even when a large model pack is not installed."
        )
        note.setWordWrap(True)
        note.setObjectName("Muted")
        outer.addWidget(note)

        status_card = QFrame()
        status_card.setObjectName("Card")
        status_layout = QVBoxLayout(status_card)
        status_layout.addWidget(QLabel("INSTALLED TOOLS"))
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("Muted")
        status_layout.addWidget(self.status)
        refresh = QPushButton("Refresh Tool Status")
        refresh.clicked.connect(self.refresh_status)
        status_layout.addWidget(refresh)
        outer.addWidget(status_card)

        source_card = QFrame()
        source_card.setObjectName("Card")
        sl = QVBoxLayout(source_card)
        sl.addWidget(QLabel("SOURCE"))
        self.source = QComboBox()
        sl.addWidget(self.source)
        outer.addWidget(source_card)

        actions = QFrame()
        actions.setObjectName("Card")
        al = QVBoxLayout(actions)
        al.addWidget(QLabel("OPERATIONS"))
        buttons = [
            ("Split into Open-Unmix stems", self.split_stems),
            ("Clean / denoise with DeepFilterNet", self.clean_vocal),
            ("Transcribe lyrics + word timestamps", self.transcribe),
            ("Convert melody/audio to MIDI", self.to_midi),
        ]
        for text, callback in buttons:
            button = QPushButton(text)
            button.clicked.connect(callback)
            al.addWidget(button)
        outer.addWidget(actions)
        outer.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        outer.addWidget(close)
        self.refresh_sources()
        self.refresh_status()

    def refresh_sources(self):
        self.project._ensure_v2_slots()
        self.source.clear()
        for source in self.project.sources:
            if source.path and Path(source.path).is_file():
                self.source.addItem(f"{source.role} — {source.label or Path(source.path).name}", source.path)
        if self.project.build_path and Path(self.project.build_path).is_file():
            self.source.addItem("Build", self.project.build_path)
        if self.project.master_path and Path(self.project.master_path).is_file():
            self.source.addItem("Master", self.project.master_path)

    def refresh_status(self):
        statuses = tool_statuses()
        self.status.setText("\n".join(
            f"{'✓' if item.available else '○'} {item.name}: {item.detail}"
            for item in statuses
        ))

    def selected_path(self) -> str:
        path = str(self.source.currentData() or "")
        if not path:
            raise ValueError("Choose an audio source first.")
        return path

    def _busy(self, active: bool):
        if active:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents()

    def split_stems(self):
        try:
            self._busy(True)
            folders = ensure_project_folders(self.project, self.main.project_path)
            outputs = separate_open_unmix(self.selected_path(), folders.stems / Path(self.selected_path()).stem)
            self.project.settings["last_stem_outputs"] = [str(p) for p in outputs]
            self.main.snapshot("Separated stems")
            QMessageBox.information(self, "Stems ready", f"Created {len(outputs)} stem file(s).")
        except Exception as exc:
            QMessageBox.critical(self, "Stem separation failed", str(exc))
        finally:
            self._busy(False)

    def clean_vocal(self):
        try:
            self._busy(True)
            folders = ensure_project_folders(self.project, self.main.project_path)
            output = clean_vocal_deepfilter(self.selected_path(), folders.generated / "Cleaned Vocals")
            self.project.settings["last_cleaned_audio"] = str(output)
            self.main.snapshot("Cleaned audio")
            QMessageBox.information(self, "Cleanup complete", str(output))
        except Exception as exc:
            QMessageBox.critical(self, "Cleanup failed", str(exc))
        finally:
            self._busy(False)

    def transcribe(self):
        try:
            self._busy(True)
            result = transcribe_faster_whisper(self.selected_path())
            self.project.lyrics = result.text
            folders = ensure_project_folders(self.project, self.main.project_path)
            transcript = folders.lyrics / "transcription.txt"
            transcript.write_text(result.text, encoding="utf-8")
            if result.words:
                lrc = folders.lyrics / "word-timestamps.lrc"
                lrc.write_text(words_to_lrc(result.words), encoding="utf-8")
                self.project.settings["whisper_word_lrc"] = str(lrc)
            self.project.settings["transcription_language"] = result.language
            self.main.snapshot("Transcribed lyrics")
            self.main.sync_ui_from_project()
            QMessageBox.information(self, "Transcription complete", str(transcript))
        except Exception as exc:
            QMessageBox.critical(self, "Transcription failed", str(exc))
        finally:
            self._busy(False)

    def to_midi(self):
        try:
            self._busy(True)
            folders = ensure_project_folders(self.project, self.main.project_path)
            midi = audio_to_midi(self.selected_path(), folders.generated / "MIDI")
            self.project.settings["last_midi"] = str(midi)
            self.main.snapshot("Converted audio to MIDI")
            QMessageBox.information(self, "MIDI ready", str(midi))
        except Exception as exc:
            QMessageBox.critical(self, "MIDI conversion failed", str(exc))
        finally:
            self._busy(False)
