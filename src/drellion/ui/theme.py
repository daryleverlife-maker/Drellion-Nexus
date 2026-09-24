APP_QSS = '''
QWidget { background: #0f1117; color: #f3f5f7; font-family: Segoe UI; font-size: 10.5pt; }
QMainWindow { background: #0f1117; }
QFrame#Card { background: #171a22; border: 1px solid #2c3240; border-radius: 12px; }
QLabel#Muted { color: #9aa4b2; }
QLabel#PageTitle { font-size: 20pt; font-weight: 750; }
QPushButton { background: #202431; border: 1px solid #353c4c; border-radius: 8px; padding: 8px 14px; min-height: 28px; }
QPushButton:hover { background: #292f3e; }
QPushButton:focus { border: 2px solid #b8aaff; }
QPushButton#Primary { background: #7c5cff; border: none; font-weight: 600; }
QPushButton#Primary:hover { background: #9278ff; }
QLineEdit, QTextEdit, QComboBox, QListWidget, QSpinBox { background: #11141b; border: 1px solid #343b4a; border-radius: 8px; padding: 7px; }
QScrollArea { border: 0; }
'''

LIGHT_QSS = '''
QWidget { background: #f6f7fb; color: #151821; font-family: Segoe UI; font-size: 10.5pt; }
QMainWindow { background: #f6f7fb; }
QGroupBox, QFrame#Card { background: #ffffff; border: 1px solid #ccd2dd; border-radius: 12px; }
QLabel#Muted { color: #596273; }
QLabel#PageTitle { font-size: 20pt; font-weight: 750; }
QPushButton { background: #ffffff; border: 1px solid #aab2c0; border-radius: 8px; padding: 8px 14px; min-height: 28px; }
QPushButton:hover { background: #eceff5; }
QPushButton:focus { border: 2px solid #4d35d9; }
QPushButton#Primary { background: #6047e8; color: white; border: none; font-weight: 600; }
QLineEdit, QTextEdit, QComboBox, QListWidget, QSpinBox { background: white; color:#151821; border: 1px solid #aab2c0; border-radius: 8px; padding: 7px; }
'''

HIGH_CONTRAST_QSS = '''
QWidget { background: #000000; color: #ffffff; font-family: Segoe UI; font-size: 11pt; }
QMainWindow { background: #000000; }
QGroupBox, QFrame#Card { background: #000000; border: 2px solid #ffffff; border-radius: 6px; }
QLabel#Muted { color: #ffffff; }
QLabel#PageTitle { font-size: 21pt; font-weight: 800; }
QPushButton { background: #000000; color:#ffffff; border: 2px solid #ffffff; border-radius: 6px; padding: 10px 16px; min-height: 34px; }
QPushButton:focus { border: 3px solid #ffff00; }
QPushButton#Primary { background: #ffff00; color: #000000; font-weight: 800; }
QLineEdit, QTextEdit, QComboBox, QListWidget, QSpinBox { background: #000000; color:#ffffff; border: 2px solid #ffffff; border-radius: 5px; padding: 8px; }
'''


def stylesheet_for(settings) -> str:
    theme = getattr(settings, "theme", "Dark")
    base = HIGH_CONTRAST_QSS if theme == "High Contrast" or getattr(settings, "high_contrast", False) else LIGHT_QSS if theme == "Light" else APP_QSS
    scale = max(100, min(200, int(getattr(settings, "text_scale", 100)))) / 100.0
    font = getattr(settings, "font_family", "System")
    family = "Segoe UI" if font == "System" else font
    extra = f'\nQWidget {{ font-family: "{family}"; font-size: {10.5*scale:.2f}pt; }}\n'
    if getattr(settings, "large_controls", False):
        extra += "QPushButton, QLineEdit, QComboBox, QSpinBox { min-height: 42px; padding: 10px 16px; }\n"
    if getattr(settings, "enhanced_focus", True):
        extra += "QWidget:focus { outline: 2px solid #ffff00; }\n"
    return base + extra
