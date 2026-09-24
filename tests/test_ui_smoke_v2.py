import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication,QPushButton
from drellion.ui.main_window import MainWindow

def test_main_window_contains_v2_workflow():
    app=QApplication.instance() or QApplication([]); window=MainWindow(); expected={"Home","Project","Sources","References","Direction","Previews","Build","Master","Studio","Export","Versions","Project Files","Lyrics & Timing","AI Engines","Project Health","Storage"}; assert expected.issubset(window.pages); texts=[button.text() for button in window.findChildren(QPushButton)]; assert any("Accessibility" in text for text in texts); assert "A/B Reference" in texts; assert "Transcribe Lead Vocal (Whisper)" in texts; window.close()
