from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..health import project_health


class HealthDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent or main)
        self.main = main
        self.setWindowTitle("Drellion Nexus — Project Check")
        self.resize(720, 620)
        self.outer = QVBoxLayout(self)
        title = QLabel("PROJECT CHECK")
        title.setStyleSheet("font-size:18pt;font-weight:700;")
        self.outer.addWidget(title)
        self.content = QVBoxLayout()
        self.outer.addLayout(self.content)
        self.outer.addStretch(1)
        bottom = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        bottom.addWidget(refresh)
        bottom.addStretch(1)
        bottom.addWidget(close)
        self.outer.addLayout(bottom)
        self.refresh()

    def refresh(self):
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for check in project_health(self.main.project, self.main.project_path):
            card = QFrame()
            card.setObjectName("Card")
            row = QHBoxLayout(card)
            symbol = "✓" if check.ok else ("⚠" if check.warning else "✕")
            status = QLabel(symbol)
            status.setStyleSheet("font-size:16pt;font-weight:700;")
            row.addWidget(status)
            name = QLabel(check.name)
            name.setStyleSheet("font-weight:650;")
            row.addWidget(name)
            detail = QLabel(check.detail)
            detail.setWordWrap(True)
            detail.setObjectName("Muted")
            row.addWidget(detail, 1)
            self.content.addWidget(card)
