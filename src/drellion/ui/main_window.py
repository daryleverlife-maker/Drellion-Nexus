from pathlib import Path
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from ..autosave import write_autosave
from ..engine import NexusEngine
from ..history import History
from ..project import ProjectState
from .player import PlayerBar
from .theme import APP_QSS
from .steps import (
    VocalLyricsStep, ReferenceStep, SoundsStep, PreviewStep, BuildStep, MasterStep,
)
from .studio import StudioWindow


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

        self.project = ProjectState()
        self.project_path = None
        self.history = History(self.project)
        self.engine = NexusEngine()
        self.current_step = 0

        self.build_ui()
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

        mode = QPushButton("AI AUTO")
        mode.setObjectName("Primary")
        top.addWidget(mode)
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

    def new_project(self):
        self.project = ProjectState()
        self.project_path = None
        self.history = History(self.project)
        self.refresh_summary()
        self.goto_step(0)

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Drellion Project", "", "Drellion Project (*.drellion)"
        )
        if not path:
            return
        try:
            self.project = ProjectState.load(path)
            self.project_path = Path(path)
            self.history = History(self.project)
            self.refresh_summary()
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def save_project(self):
        if self.project_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Drellion Project", "", "Drellion Project (*.drellion)"
            )
            if not path:
                return
            self.project_path = Path(path)
        self.project_path = self.project.save(self.project_path)
        self.refresh_summary()

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
            self.refresh_summary()

    def redo(self):
        state = self.history.redo()
        if state is not None:
            self.project = state
            self.refresh_summary()
