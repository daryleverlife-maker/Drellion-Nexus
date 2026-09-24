from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ..accessibility import AccessibilitySettings

DARK = """
QWidget { background: #11151c; color: #edf2f7; }
QMainWindow, QDialog { background: #0d1117; }
QPushButton { background: #263241; border: 1px solid #53657a; border-radius: 7px; padding: 8px 12px; min-height: 24px; }
QPushButton:hover { background: #314156; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QListWidget:focus, QTableWidget:focus { border: 2px solid #9bd6ff; }
QPushButton[primary="true"] { background: #1769aa; border-color: #6cb8ef; font-weight: 600; }
QPushButton[warning="true"] { background: #5a4215; border-color: #d3a646; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget, QListWidget, QTreeWidget { background: #171d26; border: 1px solid #425066; border-radius: 5px; padding: 5px; }
QHeaderView::section { background: #202a36; color: #edf2f7; padding: 6px; border: 0; }
QGroupBox { border: 1px solid #334155; border-radius: 8px; margin-top: 10px; padding-top: 14px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QTabWidget::pane { border: 1px solid #334155; }
QTabBar::tab { background: #1b2430; padding: 8px 12px; margin-right: 2px; }
QTabBar::tab:selected { background: #2a394b; }
QSlider::groove:horizontal { height: 6px; background: #344155; border-radius: 3px; }
QSlider::handle:horizontal { width: 18px; margin: -6px 0; border-radius: 9px; background: #c5e7ff; }
QProgressBar { border: 1px solid #425066; border-radius: 5px; text-align: center; }
QProgressBar::chunk { background: #2e7dba; }
QToolTip { background: #f8fafc; color: #111827; border: 1px solid #6b7280; }
"""
LIGHT = """
QWidget { background: #f6f8fb; color: #16202d; }
QMainWindow, QDialog { background: #ffffff; }
QPushButton { background: #eef2f7; border: 1px solid #8aa0b6; border-radius: 7px; padding: 8px 12px; min-height: 24px; }
QPushButton:hover { background: #dfe7f0; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QListWidget:focus, QTableWidget:focus { border: 2px solid #145da0; }
QPushButton[primary="true"] { background: #1263a5; color: white; font-weight: 600; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget, QListWidget, QTreeWidget { background: #ffffff; border: 1px solid #9aabba; border-radius: 5px; padding: 5px; }
QHeaderView::section { background: #e7edf3; padding: 6px; border: 0; }
QGroupBox { border: 1px solid #b3c0cd; border-radius: 8px; margin-top: 10px; padding-top: 14px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QSlider::groove:horizontal { height: 6px; background: #c7d2df; border-radius: 3px; }
QSlider::handle:horizontal { width: 18px; margin: -6px 0; border-radius: 9px; background: #145da0; }
"""
HIGH_CONTRAST = """
QWidget { background: #000000; color: #ffffff; }
QPushButton, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget, QListWidget, QTreeWidget { background: #000000; color: #ffffff; border: 2px solid #ffffff; border-radius: 2px; padding: 7px; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QListWidget:focus, QTableWidget:focus { border: 3px solid #ffff00; }
QPushButton[primary="true"] { background: #ffffff; color: #000000; font-weight: 700; }
QGroupBox { border: 2px solid #ffffff; margin-top: 10px; padding-top: 14px; }
QHeaderView::section { background: #000000; color: #ffffff; border: 1px solid #ffffff; padding: 6px; }
QSlider::groove:horizontal { height: 8px; background: #ffffff; }
QSlider::handle:horizontal { width: 22px; margin: -7px 0; background: #ffff00; }
"""


def apply_accessibility(app: QApplication, settings: AccessibilitySettings) -> None:
    base = app.font()
    if settings.font_family not in {"System","Atkinson Hyperlegible","Atkinson Hyperlegible Next","OpenDyslexic"}: family=settings.font_family
    elif settings.font_family=="System": family=base.family()
    else: family=settings.font_family
    point=max(8.0,base.pointSizeF()*settings.text_scale/100.0); app.setFont(QFont(family,int(round(point))))
    theme=settings.theme.lower(); base_sheet=HIGH_CONTRAST if "contrast" in theme else LIGHT if theme=="light" else DARK
    scale=max(1.0,settings.ui_scale/100.0); size_factor={"Normal":1.0,"Large":1.12,"Extra Large":1.28}.get(settings.control_size,1.0)
    min_height=int(round(30*scale*size_factor)); padding_v=max(5,int(round(6*scale))); padding_h=max(8,int(round(10*scale)))
    base_sheet+=f"\nQPushButton, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ min-height: {min_height}px; padding: {padding_v}px {padding_h}px; }}"
    if settings.focus=="Enhanced": base_sheet+="\n*:focus { outline: none; } QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QListWidget:focus, QTableWidget:focus { border-width: 3px; }"
    app.setStyleSheet(base_sheet)
