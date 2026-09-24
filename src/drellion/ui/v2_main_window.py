from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox

from ..accessibility import AccessibilitySettings
from ..autosave import write_autosave
from ..project import ProjectState
from ..storage import StorageSettings
from .theme import stylesheet_for
from .v2_workspace import V2Workspace


class V2MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drellion Nexus 2.0")
        self.resize(1500, 940)
        self.setMinimumSize(1100, 720)
        self.project = ProjectState()
        self.project_path: Path | None = None
        self.storage = StorageSettings.defaults()
        self.storage.ensure()
        self.accessibility = AccessibilitySettings()
        self.setStyleSheet(stylesheet_for(self.accessibility))

        self.workspace = V2Workspace(self.project, self.storage, self.accessibility, self)
        self.setCentralWidget(self.workspace)
        self._menus()

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(30000)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start()

    def _menus(self):
        file_menu = self.menuBar().addMenu("&File")
        for title, shortcut, callback in (
            ("New Project", QKeySequence.New, self.new_project),
            ("Open…", QKeySequence.Open, self.open_project),
            ("Save", QKeySequence.Save, self.save_project),
            ("Save As…", QKeySequence.SaveAs, self.save_project_as),
            ("Open Project Folder", None, self.open_project_folder),
        ):
            action = QAction(title, self)
            if shortcut: action.setShortcut(shortcut)
            action.triggered.connect(callback)
            file_menu.addAction(action)

        view_menu = self.menuBar().addMenu("&View")
        accessibility = QAction("Accessibility…", self)
        accessibility.triggered.connect(self.workspace.open_accessibility)
        view_menu.addAction(accessibility)

    def _sync(self):
        self.workspace.sync()
        self.project.touch()

    def _replace_project(self, project: ProjectState):
        self.project = project
        old = self.workspace
        self.workspace = V2Workspace(self.project, self.storage, self.accessibility, self)
        self.setCentralWidget(self.workspace)
        old.deleteLater()

    def new_project(self):
        self._replace_project(ProjectState())
        self.project_path = None

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Drellion Project", "", "Drellion Project (*.drellion)")
        if not path: return
        try:
            project = ProjectState.load(path)
            self.project_path = Path(path)
            project.ensure_layout(self.project_path.parent)
            self._replace_project(project)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def save_project(self):
        if self.project_path is None:
            return self.save_project_as()
        self._sync()
        self.project.ensure_layout(self.project_path.parent)
        self.project.save(self.project_path)

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Drellion Project", "", "Drellion Project (*.drellion)")
        if not path: return
        self._sync()
        target = Path(path)
        if target.suffix.lower() != ".drellion":
            target = target.with_suffix(".drellion")
        self.project_path = target
        self.project.ensure_layout(target.parent)
        self.project.save(target)

    def open_project_folder(self):
        self._sync()
        folders = self.project.ensure_layout(self.project_path.parent if self.project_path else None)
        QMessageBox.information(self, "Project Folder", str(folders["root"]))

    def autosave(self):
        try:
            self._sync()
            root = self.project.ensure_layout(self.project_path.parent if self.project_path else None)
            write_autosave(self.project, self.project_path, root["autosaves"])
        except Exception:
            pass
