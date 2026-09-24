from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox

from ..accessibility import AccessibilitySettings
from ..autosave import write_autosave
from ..project import ProjectState
from ..history import History
from ..storage import StorageSettings
from .theme import stylesheet_for
from .v2_workspace import V2Workspace


class V2MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drellion Nexus 2.0")
        self.resize(1500, 940)
        self.setMinimumSize(1100, 720)
        self.setAcceptDrops(True)
        self.settings_root = Path.home() / ".drellion"
        self.settings_root.mkdir(parents=True, exist_ok=True)
        self.project = ProjectState()
        self.project_path: Path | None = None
        self.storage = StorageSettings.load(self.settings_root / "storage.json")
        self.storage.ensure()
        self.accessibility = AccessibilitySettings.load(self.settings_root / "accessibility.json")
        self.history = History(self.project)
        self.setStyleSheet(stylesheet_for(self.accessibility))

        self.workspace = V2Workspace(self.project, self.storage, self.accessibility, self)
        self.workspace.open_project_requested.connect(self.load_project_path)
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
            ("Save Copy…", None, self.save_copy),
            ("Open Project Folder", None, self.open_project_folder),
        ):
            action = QAction(title, self)
            if shortcut: action.setShortcut(shortcut)
            action.triggered.connect(callback)
            file_menu.addAction(action)

        edit_menu = self.menuBar().addMenu("&Edit")
        undo_action = QAction("Undo", self); undo_action.setShortcut(QKeySequence.Undo); undo_action.triggered.connect(self.undo); edit_menu.addAction(undo_action)
        redo_action = QAction("Redo", self); redo_action.setShortcut(QKeySequence.Redo); redo_action.triggered.connect(self.redo); edit_menu.addAction(redo_action)
        edit_menu.addSeparator()
        checkpoint_action = QAction("Create History Point", self); checkpoint_action.triggered.connect(lambda: self.checkpoint("Manual history point")); edit_menu.addAction(checkpoint_action)
        clear_generated = QAction("Clear Generated Outputs", self); clear_generated.triggered.connect(self.clear_generated); edit_menu.addAction(clear_generated)
        reset_action = QAction("Reset Project…", self); reset_action.triggered.connect(self.reset_project); edit_menu.addAction(reset_action)

        view_menu = self.menuBar().addMenu("&View")
        accessibility = QAction("Accessibility…", self)
        accessibility.triggered.connect(self.workspace.open_accessibility)
        view_menu.addAction(accessibility)

    def _sync(self):
        self.workspace.sync()
        self.project.touch()

    def checkpoint(self, label: str):
        self._sync()
        self.history.push(label, self.project)

    def _replace_project(self, project: ProjectState, reset_history: bool = True):
        self.project = project
        if reset_history:
            self.history = History(self.project)
        old = self.workspace
        self.workspace = V2Workspace(self.project, self.storage, self.accessibility, self)
        self.workspace.open_project_requested.connect(self.load_project_path)
        self.setCentralWidget(self.workspace)
        old.deleteLater()

    def new_project(self):
        self._replace_project(ProjectState())
        self.project_path = None

    def load_project_path(self, path: str | Path):
        try:
            project = ProjectState.load(path)
            self.project_path = Path(path)
            project.ensure_layout(self.project_path.parent)
            self._replace_project(project)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

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
        self.history.push("Saved project", self.project)

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

    def save_copy(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project Copy", "", "Drellion Project (*.drellion)")
        if not path:
            return
        self._sync()
        self.project.save(path)

    def undo(self):
        state = self.history.undo()
        if state is not None:
            self._replace_project(state, reset_history=False)

    def redo(self):
        state = self.history.redo()
        if state is not None:
            self._replace_project(state, reset_history=False)

    def clear_generated(self):
        self.checkpoint("Before clearing generated outputs")
        self.project.selected_preview = ""
        self.project.build_path = ""
        self.project.master_path = ""
        for key in ("selected_preview_seed","selected_preview_provider","selected_preview_path","build_provider","build_report","master_report","generated_stems"):
            self.project.settings.pop(key, None)
        self._replace_project(self.project, reset_history=False)

    def reset_project(self):
        answer = QMessageBox.question(self, "Reset Project", "Reset the project to defaults? Imported files on disk will not be deleted.")
        if answer != QMessageBox.Yes:
            return
        self.checkpoint("Before project reset")
        self._replace_project(ProjectState())
        self.project_path = None

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


    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if not paths:
            return
        try:
            for path in paths:
                if path.suffix.lower() == ".drellion" and path.is_file():
                    project = ProjectState.load(path)
                    self.project_path = path
                    self._replace_project(project)
                    event.acceptProposedAction()
                    return
                if path.is_dir():
                    # Library page is index 8 in the v2 navigation.
                    if self.workspace.stack.currentIndex() == 8:
                        self.project.sound_library_path = str(path)
                        self.workspace.library_page.path.setText(str(path))
                        self.workspace.library_page.refresh()
                    continue
                if path.suffix.lower() in {".wav",".flac",".mp3",".m4a",".aac",".ogg",".opus",".aiff",".aif",".wma"}:
                    if self.workspace.stack.currentIndex() == 2 and len(self.project.references) < 6:
                        self.project.add_reference(path=str(path), title=path.stem)
                        self.workspace.references.refresh()
                    else:
                        role = "Full Song" if self.project.settings.get("start_mode") in ("Full Song","Multiple Songs / Mashup") else "Other"
                        if not self.project.sources and role == "Other":
                            role = "Lead Vocal"
                        self.project.add_source(path=str(path), role=role, label=path.name)
                        self.workspace.sources.refresh()
            self.project.touch()
            event.acceptProposedAction()
        except Exception as exc:
            QMessageBox.critical(self, "Drop failed", str(exc))

    def closeEvent(self, event):
        try:
            self._sync()
            self.storage.save(self.settings_root / "storage.json")
            self.accessibility.save(self.settings_root / "accessibility.json")
        except Exception:
            pass
        super().closeEvent(event)
