import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication
from drellion.ui.main_window import MainWindow


def test_main_window_smoke():
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    assert window.windowTitle()=="Drellion Nexus"
    assert len(window.steps)==6
    assert window.STEP_TITLES[0].startswith("1")
    assert window.STEP_TITLES[-1].startswith("6")
    window.close()
