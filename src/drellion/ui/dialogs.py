from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,QComboBox,QDialog,QDialogButtonBox,QFileDialog,QFormLayout,QHBoxLayout,
    QLabel,QLineEdit,QPushButton,QSpinBox,QVBoxLayout,
)

from ..accessibility import AccessibilitySettings, save_accessibility_settings
from ..storage import default_projects_dir
from .theme import apply_accessibility


class NewProjectDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle("New Drellion Project"); self.resize(620,330)
        root=QVBoxLayout(self); heading=QLabel("NEW PROJECT"); heading.setStyleSheet("font-size:22px;font-weight:700;")
        form=QFormLayout(); self.title=QLineEdit("My New Song"); self.artist=QLineEdit(); self.location=QLineEdit(str(default_projects_dir())); choose=QPushButton("Change Folder"); holder=QHBoxLayout(); holder.addWidget(self.location,1); holder.addWidget(choose)
        self.mode=QComboBox(); self.mode.addItems(["Vocal / Acapella","Vocal + Stems","Full Song","Multiple Songs / Mashup Project","Instrumental","Lyrics Only","Empty Studio"])
        self.keep=QCheckBox("Keep imported files inside project"); self.keep.setChecked(True); self.autosave=QSpinBox(); self.autosave.setRange(30,900); self.autosave.setValue(120); self.autosave.setSuffix(" seconds")
        form.addRow("Project name",self.title); form.addRow("Artist",self.artist); form.addRow("Save project to",holder); form.addRow("Start from",self.mode); form.addRow(self.keep); form.addRow("Autosave every",self.autosave)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Create Project"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); choose.clicked.connect(self.choose_folder)
        root.addWidget(heading); root.addLayout(form); root.addStretch(); root.addWidget(buttons)
    def choose_folder(self):
        folder=QFileDialog.getExistingDirectory(self,"Project parent folder",self.location.text())
        if folder:self.location.setText(folder)
    def values(self):
        return {"title":self.title.text().strip() or "Untitled","artist":self.artist.text().strip(),"parent":self.location.text().strip(),"mode":self.mode.currentText(),"keep":self.keep.isChecked(),"autosave_seconds":self.autosave.value()}


class AccessibilityDialog(QDialog):
    def __init__(self,app,settings:AccessibilitySettings,parent=None):
        super().__init__(parent); self.app=app; self.settings=settings; self.setWindowTitle("Accessibility Center"); self.resize(560,620)
        root=QVBoxLayout(self); heading=QLabel("ACCESSIBILITY"); heading.setStyleSheet("font-size:22px;font-weight:700;")
        form=QFormLayout(); self.ui_scale=QComboBox(); self.ui_scale.addItems(["100","125","150","175","200"]); self.ui_scale.setCurrentText(str(settings.ui_scale)); self.text_scale=QComboBox(); self.text_scale.addItems(["100","125","150","175","200"]); self.text_scale.setCurrentText(str(settings.text_scale)); self.font=QComboBox(); self.font.addItems(["System","Atkinson Hyperlegible Next","OpenDyslexic"]); self.font.setCurrentText(settings.font_family); self.density=QComboBox(); self.density.addItems(["Comfortable","Compact"]); self.density.setCurrentText(settings.density); self.theme=QComboBox(); self.theme.addItems(["Dark","Light","High Contrast"]); self.theme.setCurrentText(settings.theme); self.color=QComboBox(); self.color.addItems(["Default","Deuteranopia","Protanopia","Tritanopia"]); self.color.setCurrentText(settings.color_vision); self.focus=QComboBox(); self.focus.addItems(["Standard","Enhanced"]); self.focus.setCurrentText(settings.focus); self.motion=QComboBox(); self.motion.addItems(["Normal","Reduced","None"]); self.motion.setCurrentText(settings.motion); self.screen=QComboBox(); self.screen.addItems(["Auto","Enhanced spoken feedback"]); self.screen.setCurrentText(settings.screen_reader); self.keyboard=QCheckBox("Keyboard-only workflow emphasis"); self.keyboard.setChecked(settings.keyboard_only); self.controls=QComboBox(); self.controls.addItems(["Normal","Large","Extra Large"]); self.controls.setCurrentText(settings.control_size); self.wave=QComboBox(); self.wave.addItems(["Normal","Enhanced"]); self.wave.setCurrentText(settings.waveform_contrast); self.meter=QComboBox(); self.meter.addItems(["Color + numeric","Numeric only"]); self.meter.setCurrentText(settings.meter_mode); self.spoken=QCheckBox("Spoken playhead / track / marker feedback"); self.spoken.setChecked(settings.spoken_feedback)
        for label,widget in (("UI scale",self.ui_scale),("Text scale",self.text_scale),("Font",self.font),("UI density",self.density),("Theme",self.theme),("Color vision",self.color),("Focus",self.focus),("Motion",self.motion),("Screen reader",self.screen),("Control size",self.controls),("Waveform contrast",self.wave),("Meter mode",self.meter)): form.addRow(label,widget)
        form.addRow(self.keyboard); form.addRow(self.spoken)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Save); buttons.accepted.connect(self.apply); buttons.rejected.connect(self.reject)
        root.addWidget(heading); root.addLayout(form); root.addStretch(); root.addWidget(buttons)
    def apply(self):
        s=self.settings; s.ui_scale=int(self.ui_scale.currentText()); s.text_scale=int(self.text_scale.currentText()); s.font_family=self.font.currentText(); s.density=self.density.currentText(); s.theme=self.theme.currentText(); s.color_vision=self.color.currentText(); s.focus=self.focus.currentText(); s.motion=self.motion.currentText(); s.screen_reader=self.screen.currentText(); s.keyboard_only=self.keyboard.isChecked(); s.control_size=self.controls.currentText(); s.waveform_contrast=self.wave.currentText(); s.meter_mode=self.meter.currentText(); s.spoken_feedback=self.spoken.isChecked(); save_accessibility_settings(s); apply_accessibility(self.app,s); self.accept()
