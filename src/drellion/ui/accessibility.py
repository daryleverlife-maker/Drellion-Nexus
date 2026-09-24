from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QVBoxLayout,
)


DEFAULTS = {
    'ui_scale': 100,
    'text_scale': 100,
    'font': 'System',
    'theme': 'Dark',
    'high_contrast': False,
    'reduced_motion': False,
    'large_controls': False,
    'enhanced_focus': True,
    'screen_reader_feedback': True,
}


def accessibility_settings(project) -> dict:
    current = dict(DEFAULTS)
    current.update(project.settings.get('accessibility', {}) or {})
    return current


def apply_accessibility(app: QApplication, project=None) -> None:
    cfg = accessibility_settings(project) if project is not None else dict(DEFAULTS)
    text_scale = max(80, min(250, int(cfg['text_scale'])))
    ui_scale = max(80, min(250, int(cfg['ui_scale'])))
    point = max(8.0, 10.5 * text_scale / 100.0)

    requested = str(cfg.get('font', 'System'))
    families = set(QFontDatabase.families())
    if requested == 'Atkinson Hyperlegible' and 'Atkinson Hyperlegible' in families:
        family = requested
    elif requested == 'OpenDyslexic' and 'OpenDyslexic' in families:
        family = requested
    else:
        family = QApplication.font().family()

    app.setFont(QFont(family, round(point)))

    theme = str(cfg.get('theme', 'Dark'))
    high = bool(cfg.get('high_contrast')) or theme == 'High Contrast'
    light = theme == 'Light'
    if high:
        bg, card, field, text, muted, border, accent = '#000000', '#090909', '#000000', '#ffffff', '#ffffff', '#ffffff', '#ffff00'
    elif light:
        bg, card, field, text, muted, border, accent = '#f4f6fa', '#ffffff', '#ffffff', '#111827', '#52606d', '#aab4c2', '#5b3fd6'
    else:
        bg, card, field, text, muted, border, accent = '#0f1117', '#171a22', '#11141b', '#f3f5f7', '#9aa4b2', '#353c4c', '#7c5cff'

    padding = max(6, round(8 * ui_scale / 100))
    min_height = 42 if cfg.get('large_controls') else max(30, round(32 * ui_scale / 100))
    focus_width = 3 if cfg.get('enhanced_focus') else 1

    app.setStyleSheet(f'''
        QWidget {{ background: {bg}; color: {text}; }}
        QMainWindow, QDialog {{ background: {bg}; }}
        QFrame#Card {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}
        QLabel#Muted {{ color: {muted}; }}
        QPushButton {{
            background: {card}; border: 1px solid {border}; border-radius: 8px;
            padding: {padding}px {padding + 6}px; min-height: {min_height}px;
        }}
        QPushButton:hover {{ border-color: {accent}; }}
        QPushButton:focus {{ border: {focus_width}px solid {accent}; }}
        QPushButton#Primary {{ background: {accent}; color: {'#000000' if high else '#ffffff'}; font-weight: 700; }}
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget, QSpinBox, QDoubleSpinBox {{
            background: {field}; color: {text}; border: 1px solid {border};
            border-radius: 8px; padding: {padding}px; min-height: {min_height}px;
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QListWidget:focus {{
            border: {focus_width}px solid {accent};
        }}
        QScrollArea {{ border: 0; }}
    ''')


class AccessibilityDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle('Drellion Nexus — Accessibility')
        self.resize(560, 620)
        cfg = accessibility_settings(project)

        outer = QVBoxLayout(self)
        title = QLabel('ACCESSIBILITY CENTER')
        title.setStyleSheet('font-size:18pt;font-weight:700;')
        outer.addWidget(title)
        description = QLabel(
            'These settings apply to the whole interface. Every primary workflow remains '
            'available without drag-and-drop or mouse-only controls.'
        )
        description.setWordWrap(True)
        description.setObjectName('Muted')
        outer.addWidget(description)

        form = QFormLayout()
        self.ui_scale = QSpinBox()
        self.ui_scale.setRange(80, 250)
        self.ui_scale.setSuffix('%')
        self.ui_scale.setValue(int(cfg['ui_scale']))
        form.addRow('UI scale', self.ui_scale)

        self.text_scale = QSpinBox()
        self.text_scale.setRange(80, 250)
        self.text_scale.setSuffix('%')
        self.text_scale.setValue(int(cfg['text_scale']))
        form.addRow('Text scale', self.text_scale)

        self.font = QComboBox()
        self.font.addItems(['System', 'Atkinson Hyperlegible', 'OpenDyslexic'])
        self.font.setCurrentText(str(cfg['font']))
        form.addRow('Font preference', self.font)

        self.theme = QComboBox()
        self.theme.addItems(['Dark', 'Light', 'High Contrast'])
        self.theme.setCurrentText(str(cfg['theme']))
        form.addRow('Theme', self.theme)

        outer.addLayout(form)

        self.large_controls = QCheckBox('Large controls / larger pointer targets')
        self.large_controls.setChecked(bool(cfg['large_controls']))
        self.high_contrast = QCheckBox('Force maximum contrast')
        self.high_contrast.setChecked(bool(cfg['high_contrast']))
        self.reduced_motion = QCheckBox('Reduced motion / no decorative animation')
        self.reduced_motion.setChecked(bool(cfg['reduced_motion']))
        self.enhanced_focus = QCheckBox('Enhanced keyboard focus indicator')
        self.enhanced_focus.setChecked(bool(cfg['enhanced_focus']))
        self.screen_reader = QCheckBox('Enhanced screen-reader feedback')
        self.screen_reader.setChecked(bool(cfg['screen_reader_feedback']))

        for widget in (
            self.large_controls, self.high_contrast, self.reduced_motion,
            self.enhanced_focus, self.screen_reader,
        ):
            outer.addWidget(widget)

        outer.addStretch(1)
        row = QHBoxLayout()
        reset = QPushButton('Reset')
        reset.clicked.connect(self.reset_defaults)
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        apply = QPushButton('Apply')
        apply.setObjectName('Primary')
        apply.clicked.connect(self.apply)
        row.addWidget(reset)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(apply)
        outer.addLayout(row)

    def reset_defaults(self):
        self.ui_scale.setValue(DEFAULTS['ui_scale'])
        self.text_scale.setValue(DEFAULTS['text_scale'])
        self.font.setCurrentText(DEFAULTS['font'])
        self.theme.setCurrentText(DEFAULTS['theme'])
        self.large_controls.setChecked(DEFAULTS['large_controls'])
        self.high_contrast.setChecked(DEFAULTS['high_contrast'])
        self.reduced_motion.setChecked(DEFAULTS['reduced_motion'])
        self.enhanced_focus.setChecked(DEFAULTS['enhanced_focus'])
        self.screen_reader.setChecked(DEFAULTS['screen_reader_feedback'])

    def apply(self):
        self.project.settings['accessibility'] = {
            'ui_scale': self.ui_scale.value(),
            'text_scale': self.text_scale.value(),
            'font': self.font.currentText(),
            'theme': self.theme.currentText(),
            'high_contrast': self.high_contrast.isChecked(),
            'reduced_motion': self.reduced_motion.isChecked(),
            'large_controls': self.large_controls.isChecked(),
            'enhanced_focus': self.enhanced_focus.isChecked(),
            'screen_reader_feedback': self.screen_reader.isChecked(),
        }
        self.project.touch()
        apply_accessibility(QApplication.instance(), self.project)
        self.accept()
