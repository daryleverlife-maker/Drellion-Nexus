from pathlib import Path
from PySide6.QtWidgets import QFileDialog,QComboBox,QFrame,QHBoxLayout,QLabel,QLineEdit,QListWidget,QPushButton,QTextEdit,QVBoxLayout,QWidget

class StepBase(QWidget):
    title=""
    subtitle=""
    def __init__(self,window):
        super().__init__(); self.window=window
        self.layout=QVBoxLayout(self); self.layout.setContentsMargins(8,8,8,24); self.layout.setSpacing(12)
        h=QLabel(self.title); h.setStyleSheet("font-size:22pt;font-weight:650;"); self.layout.addWidget(h)
        s=QLabel(self.subtitle); s.setWordWrap(True); s.setObjectName("Muted"); self.layout.addWidget(s)
    def card(self,title):
        f=QFrame(); f.setObjectName("Card"); l=QVBoxLayout(f); l.setContentsMargins(18,16,18,16); l.setSpacing(10)
        t=QLabel(title); t.setStyleSheet("font-size:13pt;font-weight:600;"); l.addWidget(t); self.layout.addWidget(f); return l

class VocalLyricsStep(StepBase):
    title="Start with the voice"
    subtitle="Your vocal controls melody, timing and phrasing. A completed song is optional."
    def __init__(self,window):
        super().__init__(window)
        c=self.card("Vocal stem")
        r=QHBoxLayout(); self.path=QLineEdit(); self.path.setPlaceholderText("Drop or choose a vocal stem"); r.addWidget(self.path,1)
        b=QPushButton("Choose…"); b.clicked.connect(self.choose); r.addWidget(b); c.addLayout(r)
        self.preserve=QComboBox(); self.preserve.addItems(["Natural","Polished","Flexible"]); self.preserve.setCurrentText(window.project.vocal_preservation); self.preserve.currentTextChanged.connect(self.change_preserve)
        c.addWidget(QLabel("Vocal preservation")); c.addWidget(self.preserve)
        l=self.card("Lyrics"); self.lyrics=QTextEdit(); self.lyrics.setPlaceholderText("Paste or type lyrics here. Drellion will align them to the vocal."); self.lyrics.textChanged.connect(self.lyrics_changed); l.addWidget(self.lyrics)
        self.layout.addStretch()
    def choose(self):
        p,_=QFileDialog.getOpenFileName(self,"Choose Vocal","","Audio (*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.opus *.aiff)")
        if p:
            self.path.setText(p); self.window.project.vocal.path=p; self.window.project.vocal.label=Path(p).name; self.window.snapshot("Loaded vocal")
    def change_preserve(self,v): self.window.project.vocal_preservation=v; self.window.snapshot("Changed vocal preservation")
    def lyrics_changed(self): self.window.project.lyrics=self.lyrics.toPlainText(); self.window.project.touch(); self.window.refresh_summary()

class ReferenceStep(StepBase):
    title="Choose the production direction"
    subtitle="The reference guides groove, energy, structure, tone and mix character. Its recording is never copied into the output."
    def __init__(self,window):
        super().__init__(window)
        c=self.card("Reference audio")
        r=QHBoxLayout(); self.path=QLineEdit(); self.path.setPlaceholderText("Choose a reference song"); r.addWidget(self.path,1)
        b=QPushButton("Choose…"); b.clicked.connect(self.choose); r.addWidget(b); c.addLayout(r)
        inf=QComboBox(); inf.addItems(["Light","Balanced","Strong"]); inf.setCurrentText(window.project.reference_influence); inf.currentTextChanged.connect(self.set_inf); c.addWidget(QLabel("Reference influence")); c.addWidget(inf)
        guard=QComboBox(); guard.addItems(["Standard","High","Maximum"]); guard.setCurrentText(window.project.originality_protection); guard.currentTextChanged.connect(self.set_guard); c.addWidget(QLabel("Originality protection")); c.addWidget(guard)
        self.layout.addStretch()
    def choose(self):
        p,_=QFileDialog.getOpenFileName(self,"Choose Reference","","Audio (*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.opus *.aiff)")
        if p:
            self.path.setText(p); self.window.project.reference.path=p; self.window.project.reference.label=Path(p).name; self.window.snapshot("Loaded reference")
    def set_inf(self,v): self.window.project.reference_influence=v; self.window.snapshot("Changed reference influence")
    def set_guard(self,v): self.window.project.originality_protection=v; self.window.snapshot("Changed originality protection")

class SoundsStep(StepBase):
    title="Pick the sound palette"
    subtitle="Use the Drellion library or point Nexus at another folder. User-added sounds remain refreshable."
    def __init__(self,window):
        super().__init__(window); c=self.card("Sound library")
        r=QHBoxLayout(); self.path=QLineEdit(); self.path.setPlaceholderText("Default Drellion library"); r.addWidget(self.path,1)
        b=QPushButton("Choose folder…"); b.clicked.connect(self.choose); r.addWidget(b); r.addWidget(QPushButton("Refresh")); c.addLayout(r)
        self.list=QListWidget(); self.list.addItem("Library package indexing will appear here."); c.addWidget(self.list); self.layout.addStretch()
    def choose(self):
        p=QFileDialog.getExistingDirectory(self,"Choose Sound Library")
        if p: self.path.setText(p); self.window.project.sound_library_path=p; self.window.snapshot("Changed sound library")

class PreviewStep(StepBase):
    title="Hear the arrangement before building"
    subtitle="Generate three different vocal-matched arrangements and choose one before committing to the full song."
    def __init__(self,window):
        super().__init__(window); c=self.card("Arrangement previews")
        g=QPushButton("GENERATE 3 PREVIEWS"); g.setObjectName("Primary"); g.clicked.connect(window.generate_previews); c.addWidget(g)
        for name in ("Preview A","Preview B","Preview C"):
            r=QHBoxLayout(); r.addWidget(QLabel(name)); r.addStretch(); play=QPushButton("Play"); play.clicked.connect(lambda _=False,n=name: window.play_preview(n)); r.addWidget(play); s=QPushButton("Select"); s.clicked.connect(lambda _=False,n=name:self.select(n)); r.addWidget(s); c.addLayout(r)
        self.layout.addStretch()
    def select(self,n): self.window.project.selected_preview=n; self.window.snapshot("Selected "+n)

class BuildStep(StepBase):
    title="Build the song"
    subtitle="Create the full original instrumental around your vocal and selected preview."
    def __init__(self,window):
        super().__init__(window); c=self.card("Build pipeline"); c.addWidget(QLabel("Vocal → Drums → Bass → Harmony → Arrangement → SFX → Premix")); b=QPushButton("BUILD SONG"); b.setObjectName("Primary"); b.clicked.connect(window.build_song); c.addWidget(b); self.layout.addStretch()

class MasterStep(StepBase):
    title="Master and export"
    subtitle="Finish the mix after the music works. Mastering is final polish, not the arrangement engine."
    def __init__(self,window):
        super().__init__(window); c=self.card("Master")
        t=QComboBox(); t.addItems(["-14 LUFS","-12 LUFS","-10 LUFS","-9 LUFS","Custom"]); c.addWidget(QLabel("Delivery loudness")); c.addWidget(t)
        m=QPushButton("MASTER TRACK"); m.setObjectName("Primary"); m.clicked.connect(window.master_track); c.addWidget(m)
        e=self.card("Export"); e.addWidget(QLabel("WAV • FLAC • MP3 • AAC/M4A • AIFF • OGG • OPUS • stems • lyrics/timestamps • project archive")); e.addWidget(QPushButton("Export…")); self.layout.addStretch()
