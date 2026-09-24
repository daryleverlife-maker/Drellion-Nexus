import sys
from PySide6.QtWidgets import QApplication
from .ui.v2_main_window import V2MainWindow

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Drellion Nexus 2.0")
    app.setOrganizationName("Drellion Nexus")
    window = V2MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
