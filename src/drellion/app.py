from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication
    from .ui.main_window import MainWindow
    from .ui.theme import apply_accessibility
    from .accessibility import load_accessibility_settings

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Drellion Nexus")
    app.setOrganizationName("Drellion")
    settings = load_accessibility_settings()
    apply_accessibility(app, settings)
    window = MainWindow(accessibility=settings)
    window.show()
    return app.exec()
