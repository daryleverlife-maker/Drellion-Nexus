from pathlib import Path
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QProgressDialog, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from ..auto import run_full_auto
from ..autosave import autosave_path, write_autosave
from ..engine import NexusEngine
from ..history import History
from ..project import MediaSlot, ProjectState
from .player import PlayerBar
from .advanced import AdvancedControlsDialog
from .theme import APP_QSS
from .steps import (
    VocalLyricsStep, ReferenceStep, SoundsStep, PreviewStep, BuildStep, MasterStep,
)
from .studio import StudioWindow
from .worker import FunctionThread


AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".aiff", ".aif", ".wma"}


class MainWindow(QMainWindow):
    STEP_TITLES = [
        "1  Vocal & Lyrics",
        "2  Reference",
        "3  Sounds",
        "4  Preview",
        "5  Build",
        "6  Master",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drellion Nexus")
        self.resize(1400, 900)
        self.setMinimumSize(1040, 700)
        self.setStyleSheet(APP_QSS)
        self.setAcceptDrops(True)

        self.project = ProjectState()
        self.project_path = None
        self.history = History(self.project)
        self.engine = NexusEngine()
        self.current_step = 0
        self._workers = []

        self.build_ui()
        self.build_menus()
        self.bind_shortcuts()

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(15000)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(12)

        top = QHBoxLayout()
        brand = QLabel("DRELLION NEXUS")
        brand.setStyleSheet("font-size:18pt;font-weight:700;letter-spacing:1px;")
        top.addWidget(brand)
        top.addStretch()

        for text, callback in [
            ("New", self.new_project),
            ("Open", self.open_project),
            ("Save", self.save_project),
            ("Undo", self.undo),
            ("Redo", self.redo),
        ]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            top.addWidget(button)

        self.auto_button = QPushButton("AI AUTO")
        self.auto_button.setObjectName("Primary")
        self.auto_button.clicked.connect(self.run_ai_auto)
        top.addWidget(self.auto_button)
        advanced = QPushButton("ADVANCED")
        advanced.clicked.connect(self.open_advanced)
        top.addWidget(advanced)
        studio = QPushButton("CUSTOM STUDIO")
        studio.clicked.connect(self.open_studio)
        top.addWidget(studio)
        outer.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(12)

        nav = QFrame()
        nav.setObjectName("Card")
        nav.setFixedWidth(230)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(12, 14, 12, 14)
        self.nav_buttons = []
        for index, title in enumerate(self.STEP_TITLES):
            button = QPushButton(title)
            button.clicked.connect(lambda _=False, i=index: self.goto_step(i))
            nav_layout.addWidget(button)
            self.nav_buttons.append(button)
        nav_layout.addStretch()
        body.addWidget(nav)

        self.stack = QStackedWidget()
        self.steps = [
            VocalLyricsStep(self),
            ReferenceStep(self),
            SoundsStep(self),
            PreviewStep(self),
            BuildStep(self),
            MasterStep(self),
        ]
        for step in self.steps:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(step)
            self.stack.addWidget(area)
        body.addWidget(self.stack, 1)

        side = QFrame()
        side.setObjectName("Card")
        side.setFixedWidth(280)
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel("PROJECT"))
        self.project_summary = QLabel()
        self.project_summary.setWordWrap(True)
        self.project_summary.setObjectName("Muted")
        side_layout.addWidget(self.project_summary)
        side_layout.addStretch()
        body.addWidget(side)
        outer.addLayout(body, 1)

        self.player = PlayerBar(self)
        outer.addWidget(self.player)

        self.goto_step(0)
        self.refresh_summary()

    def build_menus(self):
        file_menu = self.menuBar().addMenu("&File")

        actions = [
            ("New Project", QKeySequence.New, self.new_project),
            ("Open…", QKeySequence.Open, self.open_project),
            ("Save", QKeySequence.Save, self.save_project),
            ("Save As…", QKeySequence.SaveAs, self.save_project_as),
            ("Save Copy…", None, self.save_copy),
            ("Recover Autosave", None, self.recover_autosave),
        ]
        for title, shortcut, callback in actions:
            action = QAction(title, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(callback)
            file_menu.addAction(action)
        file_menu.addSeparator()
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()
        clear_action = QAction("Clear Current Step", self)
        clear_action.triggered.connect(self.clear_current_step)
        edit_menu.addAction(clear_action)

        reset_action = QAction("Reset Project…", self)
        reset_action.triggered.connect(self.reset_project)
        edit_menu.addAction(reset_action)

    def run_ai_auto(self):
        if not self.project.vocal.path or not self.project.reference.path:
            QMessageBox.information(
                self,
                "AI Auto",
                "Load a vocal stem and a reference track first.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Run AI Auto",
            "AI Auto will generate three arrangements, choose a direction, "
            "optionally add lyric-aware SFX, build the full song and master it.\n\n"
            "You can undo the result or continue editing it in Custom Studio. Continue?",
        )
        if answer != QMessageBox.Yes:
            return

        output = self.project_output_dir() / "Auto"
        progress = QProgressDialog(
            "Drellion Nexus is running the full AI Auto production…",
            "",
            0,
            0,
            self,
        )
        progress.setWindowTitle("AI Auto")
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        self.auto_button.setEnabled(False)
        worker = FunctionThread(run_full_auto, self.project, output, engine=self.engine)
        self._workers.append(worker)

        def cleanup():
            self.auto_button.setEnabled(True)
            progress.close()
            if worker in self._workers:
                self._workers.remove(worker)
            worker.deleteLater()

        def complete(result):
            self.project = result.state
            self.history.push("AI Auto complete", self.project)
            preview_step = self.steps[3]
            preview_step.preview_paths = {
                item.name: item.audio_path for item in result.previews
            }
            for item in result.previews:
                if item.name in preview_step.preview_descriptions:
                    preview_step.preview_descriptions[item.name].setText(item.description)
            preview_step._update_sfx_status()
            self.sync_ui_from_project()
            self.refresh_player_sources("Master")
            self.goto_step(5)
            cleanup()
            QMessageBox.information(
                self,
                "AI Auto complete",
                f"Selected: {result.chosen_preview}\n"
                f"Build: {result.build.build_path}\n"
                f"Master: {result.master_path}",
            )

        def failed(message):
            cleanup()
            QMessageBox.critical(self, "AI Auto failed", message)

        worker.completed.connect(complete)
        worker.failed.connect(failed)
        worker.start()

    def open_advanced(self):
        before = self.project.to_dict()
        dialog = AdvancedControlsDialog(self.project, self)
        if dialog.exec():
            if self.project.to_dict() != before:
                self.snapshot("Changed advanced controls")

    def open_studio(self):
        self.studio_window = StudioWindow(self)
        self.studio_window.show()

    def bind_shortcuts(self):
        QShortcut(QKeySequence.Save, self, activated=self.save_project)
        QShortcut(QKeySequence.Open, self, activated=self.open_project)
        QShortcut(QKeySequence.Undo, self, activated=self.undo)
        QShortcut(QKeySequence.Redo, self, activated=self.redo)

    def snapshot(self, label):
        self.project.touch()
        self.history.push(label, self.project)
        self.refresh_summary()

    def goto_step(self, index):
        if not 0 <= index < len(self.steps):
            return
        self.current_step = index
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setObjectName("Primary" if i == index else "")
            button.style().unpolish(button)
            button.style().polish(button)

    def project_output_dir(self) -> Path:
        if self.project_path is not None:
            root = self.project_path.parent / (self.project_path.stem + " - Renders")
        else:
            safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", self.project.name or "Untitled").strip()
            root = Path.home() / "Drellion Nexus" / "Projects" / (safe or "Untitled") / "Renders"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def refresh_player_sources(self, preferred: str | None = None):
        sources = {
            "Vocal": self.project.vocal.path,
            "Reference": self.project.reference.path,
            "Build": self.project.build_path,
            "Master": self.project.master_path,
        }
        preview_step = self.steps[3] if len(self.steps) > 3 else None
        if preview_step is not None:
            for label, path in getattr(preview_step, "preview_paths", {}).items():
                sources[label] = path
        self.player.set_sources(sources, preferred=preferred)

    def refresh_summary(self):
        p = self.project
        self.project_summary.setText(
            f"{p.name}\n\n"
            f"Vocal: {'Loaded' if p.vocal.path else 'Not loaded'}\n"
            f"Reference: {'Loaded' if p.reference.path else 'Not loaded'}\n"
            f"Sounds: {'Configured' if p.sound_library_path else 'Default library'}\n"
            f"Preview: {p.selected_preview or 'Not selected'}\n"
            f"Build: {'Ready' if p.build_path else 'Not built'}\n"
            f"Master: {'Ready' if p.master_path else 'Not mastered'}"
        )
        if hasattr(self, "player"):
            self.refresh_player_sources()

    def sync_ui_from_project(self):
        if not getattr(self, "steps", None):
            return

        vocal = self.steps[0]
        vocal.path.blockSignals(True)
        vocal.lyrics.blockSignals(True)
        vocal.preserve.blockSignals(True)
        vocal.path.setText(self.project.vocal.path)
        vocal.lyrics.setPlainText(self.project.lyrics)
        vocal.preserve.setCurrentText(self.project.vocal_preservation)
        vocal.path.blockSignals(False)
        vocal.lyrics.blockSignals(False)
        vocal.preserve.blockSignals(False)

        reference = self.steps[1]
        reference.path.setText(self.project.reference.path)

        sounds = self.steps[2]
        sounds.path.setText(self.project.sound_library_path)

        master = self.steps[5]
        target_lufs = float(self.project.settings.get("target_lufs", -14.0))
        text = f"{int(target_lufs) if target_lufs.is_integer() else target_lufs:g} LUFS"
        if master.target.findText(text) >= 0:
            master.target.setCurrentText(text)

        self.refresh_summary()

    def new_project(self):
        self.project = ProjectState()
        self.project_path = None
        self.history = History(self.project)
        self.sync_ui_from_project()
        self.goto_step(0)

    def load_project_path(self, path: str | Path):
        self.project = ProjectState.load(path)
        self.project_path = Path(path)
        self.history = History(self.project)
        self.sync_ui_from_project()

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Drellion Project", "", "Drellion Project (*.drellion)"
        )
        if not path:
            return
        try:
            self.load_project_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def save_project(self):
        if self.project_path is None:
            return self.save_project_as()
        self.project_path = self.project.save(self.project_path)
        self.refresh_summary()

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Drellion Project As", "", "Drellion Project (*.drellion)"
        )
        if not path:
            return
        self.project_path = self.project.save(path)
        self.refresh_summary()

    def save_copy(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project Copy", "", "Drellion Project (*.drellion)"
        )
        if not path:
            return
        original = self.project_path
        self.project.save(path)
        self.project_path = original
        self.refresh_summary()

    def recover_autosave(self):
        path = autosave_path(
            self.project_path,
            Path.home() / "Drellion Nexus" / "Autosaves",
        )
        if not path.is_file():
            QMessageBox.information(self, "Recover Autosave", "No autosave exists for this project.")
            return
        try:
            recovered = ProjectState.load(path)
            self.project = recovered
            self.history = History(self.project)
            self.sync_ui_from_project()
            QMessageBox.information(self, "Recover Autosave", "Autosave restored into the current project.")
        except Exception as exc:
            QMessageBox.critical(self, "Recover Autosave", str(exc))

    def autosave(self):
        try:
            write_autosave(
                self.project,
                self.project_path,
                Path.home() / "Drellion Nexus" / "Autosaves",
            )
        except Exception:
            pass

    def undo(self):
        state = self.history.undo()
        if state is not None:
            self.project = state
            self.sync_ui_from_project()

    def redo(self):
        state = self.history.redo()
        if state is not None:
            self.project = state
            self.sync_ui_from_project()

    def clear_current_step(self):
        if self.current_step == 0:
            self.project.vocal = MediaSlot()
            self.project.lyrics = ""
        elif self.current_step == 1:
            self.project.reference = MediaSlot()
        elif self.current_step == 2:
            self.project.sound_library_path = ""
            self.project.settings.pop("sound_count", None)
        elif self.current_step == 3:
            self.project.selected_preview = ""
            self.steps[3].preview_paths.clear()
        elif self.current_step == 4:
            self.project.build_path = ""
            self.project.settings.pop("generated_instrumental", None)
            self.project.settings.pop("build_report", None)
        elif self.current_step == 5:
            self.project.master_path = ""
        self.snapshot(f"Cleared step {self.current_step + 1}")
        self.sync_ui_from_project()

    def reset_project(self):
        answer = QMessageBox.question(
            self,
            "Reset Project",
            "Reset the project to defaults? Imported source files will not be deleted.",
        )
        if answer != QMessageBox.Yes:
            return
        self.project = ProjectState()
        self.history = History(self.project)
        self.sync_ui_from_project()
        self.goto_step(0)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        local_paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if not local_paths:
            return

        path = local_paths[0]
        try:
            if path.suffix.lower() == ".drellion" and path.is_file():
                self.load_project_path(path)
                event.acceptProposedAction()
                return

            if path.is_dir():
                if self.current_step == 2:
                    self.project.sound_library_path = str(path)
                    self.snapshot("Dropped sound library")
                    self.sync_ui_from_project()
                    self.steps[2].refresh()
                event.acceptProposedAction()
                return

            if path.suffix.lower() in AUDIO_EXTENSIONS:
                if self.current_step == 0:
                    self.project.vocal = MediaSlot(str(path), path.name)
                    preferred = "Vocal"
                elif self.current_step == 1:
                    self.project.reference = MediaSlot(str(path), path.name)
                    preferred = "Reference"
                elif not self.project.vocal.path:
                    self.project.vocal = MediaSlot(str(path), path.name)
                    preferred = "Vocal"
                elif not self.project.reference.path:
                    self.project.reference = MediaSlot(str(path), path.name)
                    preferred = "Reference"
                else:
                    self.project.finished_song = MediaSlot(str(path), path.name)
                    preferred = "Current"
                    self.player.load_path(str(path), "Current")
                self.snapshot(f"Dropped {preferred.lower()} audio")
                self.sync_ui_from_project()
                self.refresh_player_sources(preferred if preferred != "Current" else None)
                event.acceptProposedAction()
        except Exception as exc:
            QMessageBox.critical(self, "Drop failed", str(exc))
