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
from ..project import MediaSlot, ProjectState, SourceSlot, ReferenceSlot
from ..storage import ensure_project_folders
from ..preferences import load_preferences, apply_preferences_to_project
from ..recent import register_recent
from .player import PlayerBar
from .advanced import AdvancedControlsDialog
from .accessibility import AccessibilityDialog, apply_accessibility
from .export_center import ExportCenterDialog
from .project_setup import ProjectSetupDialog
from .health import HealthDialog
from .tools_center import ToolsCenterDialog
from .versions import VersionsDialog
from .settings import SettingsDialog
from .home import HomeDialog
from .steps import (
    VocalLyricsStep, ReferenceStep, SoundsStep, PreviewStep, BuildStep, MasterStep,
)
from .studio import StudioWindow
from .worker import FunctionThread


AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".aiff", ".aif", ".wma"}


class MainWindow(QMainWindow):
    STEP_TITLES = [
        "1  Sources & Lyrics",
        "2  Reference Board",
        "3  Direction & Engine",
        "4  Previews",
        "5  Build",
        "6  Master & Export",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drellion Nexus")
        self.resize(1400, 900)
        self.setMinimumSize(1040, 700)
        self.setAcceptDrops(True)

        self.preferences = load_preferences()
        self.project = ProjectState()
        apply_preferences_to_project(self.project, self.preferences)
        apply_accessibility(QApplication.instance(), self.project)
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
        self.autosave_timer.start(int(self.preferences.get("autosave_seconds", 120)) * 1000)

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
            ("Home", self.open_home),
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
        settings = QPushButton("SETTINGS")
        settings.clicked.connect(self.open_settings)
        top.addWidget(settings)
        accessibility = QPushButton("ACCESSIBILITY")
        accessibility.clicked.connect(self.open_accessibility)
        top.addWidget(accessibility)
        versions = QPushButton("VERSIONS")
        versions.clicked.connect(self.open_versions)
        top.addWidget(versions)
        check = QPushButton("PROJECT CHECK")
        check.clicked.connect(self.open_health)
        top.addWidget(check)
        tools = QPushButton("AI / AUDIO TOOLS")
        tools.clicked.connect(self.open_tools_center)
        top.addWidget(tools)
        export = QPushButton("EXPORT")
        export.clicked.connect(self.open_export_center)
        top.addWidget(export)
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
        self.project._ensure_v2_slots()
        has_reference = any(
            item.enabled and (item.path or item.youtube_url)
            for item in self.project.references
        )
        if not self.project.vocal.path or not has_reference:
            QMessageBox.information(
                self,
                "AI Auto",
                "Add a lead vocal and at least one enabled reference first.",
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

    def open_home(self):
        HomeDialog(self, self).exec()

    def open_settings(self):
        SettingsDialog(self, self).exec()

    def open_accessibility(self):
        before = self.project.to_dict()
        dialog = AccessibilityDialog(self.project, self)
        if dialog.exec() and self.project.to_dict() != before:
            self.snapshot("Changed accessibility settings")

    def open_versions(self):
        VersionsDialog(self, self).exec()

    def open_health(self):
        HealthDialog(self, self).exec()

    def open_tools_center(self):
        ToolsCenterDialog(self, self).exec()

    def open_export_center(self):
        ExportCenterDialog(self, self).exec()

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
        folders = ensure_project_folders(self.project, self.project_path)
        return folders.root

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
        p._ensure_v2_slots()
        sources = len([item for item in p.sources if item.path])
        references = len([item for item in p.references if item.enabled and (item.path or item.youtube_url)])
        provider = str(p.settings.get("generation_provider", "auto"))
        folder = str(ensure_project_folders(p, self.project_path).root)
        self.project_summary.setText(
            f"{p.name}\n"
            f"{p.artist or 'Artist not set'}\n\n"
            f"Sources: {sources}/6\n"
            f"References: {references}/6\n"
            f"Engine: {provider}\n"
            f"Sounds: {int(p.settings.get('sound_count', 0) or 0):,} indexed\n"
            f"Preview: {p.selected_preview or 'Not selected'}\n"
            f"Build: {'Ready' if p.build_path else 'Not built'}\n"
            f"Master: {'Ready' if p.master_path else 'Not mastered'}\n\n"
            f"Project folder:\n{folder}"
        )
        if hasattr(self, "player"):
            self.refresh_player_sources()

    def sync_ui_from_project(self):
        if not getattr(self, "steps", None):
            return

        self.project._ensure_v2_slots()
        source_step = self.steps[0]
        if hasattr(source_step, "refresh_from_project"):
            source_step.refresh_from_project()

        reference_step = self.steps[1]
        if hasattr(reference_step, "refresh_from_project"):
            reference_step.refresh_from_project()

        direction = self.steps[2]
        direction.path.setText(self.project.sound_library_path)
        direction.prompt.blockSignals(True)
        direction.prompt.setPlainText(str(self.project.settings.get("production_direction_prompt", "")))
        direction.prompt.blockSignals(False)
        direction.reference_strength.setValue(float(self.project.settings.get("reference_audio_strength", 25.0)))
        direction.ace_url.setText(str(self.project.settings.get("provider_ace_step_url", "http://127.0.0.1:8001")))
        direction.diff_url.setText(str(self.project.settings.get("provider_diff_rhythm_url", "")))
        direction.yue_url.setText(str(self.project.settings.get("provider_yue_url", "")))
        direction.basic.setChecked(bool(self.project.settings.get("enable_basic_test_engine", False)))
        provider_id = str(self.project.settings.get("generation_provider", "auto"))
        for label, value in direction.PROVIDERS.items():
            if value == provider_id:
                direction.provider.setCurrentText(label)
                break

        preview = self.steps[3]
        preview.preview_paths = dict(self.project.settings.get("preview_paths", {}) or {})
        for name, path in preview.preview_paths.items():
            if name in preview.preview_descriptions:
                preview.preview_descriptions[name].setText(Path(path).name)
        preview._update_sfx_status()

        master = self.steps[5]
        target_lufs = float(self.project.settings.get("target_lufs", -14.0))
        text = f"{int(target_lufs) if target_lufs.is_integer() else target_lufs:g} LUFS"
        if master.target.findText(text) >= 0:
            master.target.setCurrentText(text)

        apply_accessibility(QApplication.instance(), self.project)
        self.refresh_summary()

    def new_project(self):
        self.preferences = load_preferences()
        state = ProjectState()
        apply_preferences_to_project(state, self.preferences)
        dialog = ProjectSetupDialog(state, self)
        if not dialog.exec():
            return
        self.project = dialog.state
        folders = ensure_project_folders(self.project)
        self.project_path = folders.project_file
        self.project.save(self.project_path)
        register_recent(
            self.project_path,
            name=self.project.name,
            artist=self.project.artist,
            updated_at=self.project.updated_at,
        )
        self.history = History(self.project)
        self.sync_ui_from_project()
        self.goto_step(0)

    def load_project_path(self, path: str | Path):
        self.project = ProjectState.load(path)
        self.project_path = Path(path)
        register_recent(
            self.project_path,
            name=self.project.name,
            artist=self.project.artist,
            updated_at=self.project.updated_at,
        )
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
        register_recent(
            self.project_path,
            name=self.project.name,
            artist=self.project.artist,
            updated_at=self.project.updated_at,
        )
        self.refresh_summary()

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Drellion Project As", "", "Drellion Project (*.drellion)"
        )
        if not path:
            return
        self.project_path = self.project.save(path)
        register_recent(
            self.project_path,
            name=self.project.name,
            artist=self.project.artist,
            updated_at=self.project.updated_at,
        )
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
        folders = ensure_project_folders(self.project, self.project_path)
        path = autosave_path(
            self.project_path,
            folders.autosaves,
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
        if not bool(self.project.settings.get("autosave_enabled", True)):
            return
        try:
            folders = ensure_project_folders(self.project, self.project_path)
            write_autosave(
                self.project,
                self.project_path,
                folders.autosaves,
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
            self.project.sources = []
            self.project.active_vocal_source_id = ""
            self.project.vocal = MediaSlot()
            self.project.lyrics = ""
        elif self.current_step == 1:
            self.project.references = []
            self.project.active_reference_id = ""
            self.project.reference = MediaSlot()
        elif self.current_step == 2:
            self.project.settings["production_direction_prompt"] = ""
            self.project.settings["generation_provider"] = "auto"
        elif self.current_step == 3:
            self.project.selected_preview = ""
            self.project.settings["preview_paths"] = {}
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
            "Reset project content? Source files on disk will not be deleted.",
        )
        if answer != QMessageBox.Yes:
            return
        storage = self.project.storage
        accessibility = dict(self.project.settings.get("accessibility", {}) or {})
        self.project = ProjectState(name=self.project.name, artist=self.project.artist, storage=storage)
        if accessibility:
            self.project.settings["accessibility"] = accessibility
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

        try:
            for path in local_paths:
                if path.suffix.lower() == ".drellion" and path.is_file():
                    self.load_project_path(path)
                    event.acceptProposedAction()
                    return

                if path.is_dir():
                    if self.current_step == 2:
                        self.project.sound_library_path = str(path)
                        self.project.storage.sound_library_root = str(path)
                        self.snapshot("Dropped sound library")
                        self.sync_ui_from_project()
                        self.steps[2].refresh()
                    continue

                if path.suffix.lower() not in AUDIO_EXTENSIONS:
                    continue

                if self.current_step == 1:
                    step = self.steps[1]
                    target = next(
                        (item for item in self.project.references if not item.path and not item.youtube_url),
                        None,
                    )
                    if target is None:
                        target = self.project.references[-1]
                    target.path = str(path)
                    target.title = target.title or path.stem
                    target.enabled = True
                    if not self.project.active_reference_id:
                        self.project.active_reference_id = target.id
                    self.project.sync_legacy_slots()
                    step.refresh_from_project()
                    preferred = "Reference"
                else:
                    step = self.steps[0]
                    target = next((item for item in self.project.sources if not item.path), None)
                    if target is None:
                        target = self.project.sources[-1]
                    target.path = str(path)
                    target.label = path.name
                    target.enabled = True
                    if target.role == "Lead Vocal" or not self.project.vocal.path:
                        target.role = "Lead Vocal"
                        target.preserve = True
                        self.project.active_vocal_source_id = target.id
                    self.project.sync_legacy_slots()
                    step.refresh_from_project()
                    preferred = "Vocal" if target.role == "Lead Vocal" else None

                self.snapshot("Dropped source audio")
                self.refresh_player_sources(preferred)

            event.acceptProposedAction()
        except Exception as exc:
            QMessageBox.critical(self, "Drop failed", str(exc))

