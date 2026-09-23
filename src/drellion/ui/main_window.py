from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QKeySequence,QShortcut
from PySide6.QtWidgets import QFileDialog,QFrame,QHBoxLayout,QLabel,QMainWindow,QMessageBox,QPushButton,QScrollArea,QStackedWidget,QVBoxLayout,QWidget
from ..autosave import write_autosave
from ..history import History
from ..project import ProjectState
from .theme import APP_QSS
from .steps import VocalLyricsStep,ReferenceStep,SoundsStep,PreviewStep,BuildStep,MasterStep\nfrom .studio import StudioWindow

class MainWindow(QMainWindow):
    STEP_TITLES=["1  Vocal & Lyrics","2  Reference","3  Sounds","4  Preview","5  Build","6  Master"]
    def __init__(self):
        super().__init__(); self.setWindowTitle("Drellion Nexus"); self.resize(1400,900); self.setMinimumSize(1040,700); self.setStyleSheet(APP_QSS)
        self.project=ProjectState(); self.project_path=None; self.history=History(self.project); self.current_step=0
        self.build_ui(); self.bind_shortcuts(); self.autosave_timer=QTimer(self); self.autosave_timer.timeout.connect(self.autosave); self.autosave_timer.start(15000)
    def build_ui(self):
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root); outer.setContentsMargins(18,14,18,14); outer.setSpacing(12)
        top=QHBoxLayout(); brand=QLabel("DRELLION NEXUS"); brand.setStyleSheet("font-size:18pt;font-weight:700;letter-spacing:1px;"); top.addWidget(brand); top.addStretch()
        for text,cb in [("New",self.new_project),("Open",self.open_project),("Save",self.save_project),("Undo",self.undo),("Redo",self.redo)]:
            b=QPushButton(text); b.clicked.connect(cb); top.addWidget(b)
        mode=QPushButton("AI AUTO"); mode.setObjectName("Primary"); top.addWidget(mode); studio=QPushButton("CUSTOM STUDIO"); studio.clicked.connect(self.open_studio); top.addWidget(studio); outer.addLayout(top)
        body=QHBoxLayout(); body.setSpacing(12)
        nav=QFrame(); nav.setObjectName("Card"); nav.setFixedWidth(230); nl=QVBoxLayout(nav); nl.setContentsMargins(12,14,12,14); self.nav_buttons=[]
        for i,title in enumerate(self.STEP_TITLES):
            b=QPushButton(title); b.clicked.connect(lambda _=False,index=i:self.goto_step(index)); nl.addWidget(b); self.nav_buttons.append(b)
        nl.addStretch(); body.addWidget(nav)
        self.stack=QStackedWidget(); self.steps=[VocalLyricsStep(self),ReferenceStep(self),SoundsStep(self),PreviewStep(self),BuildStep(self),MasterStep(self)]
        for step in self.steps:
            area=QScrollArea(); area.setWidgetResizable(True); area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); area.setWidget(step); self.stack.addWidget(area)
        body.addWidget(self.stack,1)
        side=QFrame(); side.setObjectName("Card"); side.setFixedWidth(280); sl=QVBoxLayout(side); sl.addWidget(QLabel("PROJECT")); self.project_summary=QLabel(); self.project_summary.setWordWrap(True); self.project_summary.setObjectName("Muted"); sl.addWidget(self.project_summary); sl.addStretch(); body.addWidget(side); outer.addLayout(body,1)
        player=QFrame(); player.setObjectName("Card"); pl=QHBoxLayout(player); pl.addWidget(QLabel("PLAYER")); pl.addWidget(QPushButton("⏮")); pl.addWidget(QPushButton("▶ / ⏸")); pl.addWidget(QPushButton("■")); pl.addWidget(QLabel("00:00 / 00:00")); pl.addStretch(); pl.addWidget(QPushButton("A / B")); outer.addWidget(player)
        self.goto_step(0); self.refresh_summary()
    def open_studio(self):\n        self.studio_window=StudioWindow(self)\n        self.studio_window.show()\n\n    def bind_shortcuts(self):
        QShortcut(QKeySequence.Save,self,activated=self.save_project); QShortcut(QKeySequence.Open,self,activated=self.open_project); QShortcut(QKeySequence.Undo,self,activated=self.undo); QShortcut(QKeySequence.Redo,self,activated=self.redo)
    def snapshot(self,label): self.project.touch(); self.history.push(label,self.project); self.refresh_summary()
    def goto_step(self,index):
        if not 0<=index<len(self.steps): return
        self.current_step=index; self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav_buttons): b.setObjectName("Primary" if i==index else ""); b.style().unpolish(b); b.style().polish(b)
    def refresh_summary(self):
        p=self.project; self.project_summary.setText(f"{p.name}\n\nVocal: {'Loaded' if p.vocal.path else 'Not loaded'}\nReference: {'Loaded' if p.reference.path else 'Not loaded'}\nSounds: {'Configured' if p.sound_library_path else 'Default library'}\nPreview: {p.selected_preview or 'Not selected'}\nBuild: {'Ready' if p.build_path else 'Not built'}\nMaster: {'Ready' if p.master_path else 'Not mastered'}")
    def new_project(self): self.project=ProjectState(); self.project_path=None; self.history=History(self.project); self.refresh_summary(); self.goto_step(0)
    def open_project(self):
        p,_=QFileDialog.getOpenFileName(self,"Open Drellion Project","","Drellion Project (*.drellion)")
        if not p:return
        try:self.project=ProjectState.load(p); self.project_path=Path(p); self.history=History(self.project); self.refresh_summary()
        except Exception as e: QMessageBox.critical(self,"Open failed",str(e))
    def save_project(self):
        if self.project_path is None:
            p,_=QFileDialog.getSaveFileName(self,"Save Drellion Project","","Drellion Project (*.drellion)")
            if not p:return
            self.project_path=Path(p)
        self.project_path=self.project.save(self.project_path); self.refresh_summary()
    def autosave(self):
        try: write_autosave(self.project,self.project_path,Path.home()/"Drellion Nexus"/"Autosaves")
        except Exception: pass
    def undo(self):
        s=self.history.undo()
        if s is not None:self.project=s; self.refresh_summary()
    def redo(self):
        s=self.history.redo()
        if s is not None:self.project=s; self.refresh_summary()
