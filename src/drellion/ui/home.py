from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout,
)

from ..recent import recent_projects, remove_recent


class HomeDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent or main)
        self.main = main
        self.setWindowTitle("Drellion Nexus — Home")
        self.resize(900, 680)

        outer = QVBoxLayout(self)
        brand = QLabel("DRELLION NEXUS")
        brand.setStyleSheet("font-size:26pt;font-weight:800;letter-spacing:1px;")
        outer.addWidget(brand)
        sub = QLabel("Vocal-first production · reference-guided generation · editable Studio")
        sub.setObjectName("Muted")
        outer.addWidget(sub)

        actions = QHBoxLayout()
        new = QPushButton("+ NEW PROJECT")
        new.setObjectName("Primary")
        new.clicked.connect(self.new_project)
        open_button = QPushButton("OPEN PROJECT")
        open_button.clicked.connect(self.open_project)
        studio = QPushButton("OPEN CURRENT STUDIO")
        studio.clicked.connect(self.current_studio)
        actions.addWidget(new)
        actions.addWidget(open_button)
        actions.addWidget(studio)
        actions.addStretch(1)
        outer.addLayout(actions)

        outer.addWidget(QLabel("RECENT PROJECTS"))
        self.list = QListWidget()
        self.list.setAccessibleName("Recent Drellion Nexus projects")
        self.list.itemDoubleClicked.connect(lambda _item: self.open_selected())
        outer.addWidget(self.list, 1)

        row = QHBoxLayout()
        open_selected = QPushButton("Open Selected")
        open_selected.clicked.connect(self.open_selected)
        show = QPushButton("Show Path")
        show.clicked.connect(self.show_path)
        remove = QPushButton("Remove From Recent")
        remove.clicked.connect(self.remove_selected)
        row.addWidget(open_selected)
        row.addWidget(show)
        row.addWidget(remove)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        outer.addLayout(row)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for item in recent_projects():
            path = Path(item["path"])
            stamp = ""
            if item["updated_at"]:
                stamp = datetime.fromtimestamp(item["updated_at"]).strftime("%Y-%m-%d %H:%M")
            status = "" if path.is_file() else " · MISSING"
            label = f"{item['name']}"
            if item["artist"]:
                label += f" — {item['artist']}"
            if stamp:
                label += f" · {stamp}"
            label += status
            row = QListWidgetItem(label)
            row.setData(Qt.UserRole, item["path"])
            self.list.addItem(row)

    def selected_path(self) -> Path | None:
        item = self.list.currentItem()
        if item is None:
            return None
        return Path(str(item.data(Qt.UserRole)))

    def new_project(self):
        self.accept()
        self.main.new_project()

    def open_project(self):
        self.accept()
        self.main.open_project()

    def current_studio(self):
        self.accept()
        self.main.open_studio()

    def open_selected(self):
        path = self.selected_path()
        if path is None:
            return
        if not path.is_file():
            QMessageBox.warning(self, "Missing project", f"This project file is no longer at:\n{path}")
            return
        self.main.load_project_path(path)
        self.accept()

    def show_path(self):
        path = self.selected_path()
        if path is not None:
            QMessageBox.information(self, "Project Path", str(path))

    def remove_selected(self):
        path = self.selected_path()
        if path is not None:
            remove_recent(path)
            self.refresh()
