from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QFrame,QHBoxLayout,QLabel,QPushButton,QScrollArea,QSlider,QVBoxLayout,QWidget

class StudioWindow(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle("Drellion Nexus — Custom Studio")
        self.resize(1500,900)
        self.setModal(False)
        outer=QVBoxLayout(self)

        top=QHBoxLayout()
        title=QLabel("CUSTOM STUDIO")
        title.setStyleSheet("font-size:18pt;font-weight:700;")
        top.addWidget(title); top.addStretch()
        for name in ("Add Track","Split","Duplicate","Fade","AI Tools","Mixer","Automation"):
            top.addWidget(QPushButton(name))
        outer.addLayout(top)

        center=QHBoxLayout()
        tracks=QFrame(); tracks.setObjectName("Card"); tl=QVBoxLayout(tracks)
        tl.addWidget(QLabel("TRACKS"))
        for name in ("Vocal","Drums","Bass","Music","SFX","Generated Instrumental","Reference","Master"):
            row=QHBoxLayout(); row.addWidget(QPushButton("M")); row.addWidget(QPushButton("S")); row.addWidget(QLabel(name)); row.addStretch(); tl.addLayout(row)
        tl.addStretch()
        center.addWidget(tracks)

        timeline=QFrame(); timeline.setObjectName("Card"); timel=QVBoxLayout(timeline)
        timel.addWidget(QLabel("TIMELINE  •  Snap 1/16  •  4/4  •  120 BPM"))
        area=QScrollArea(); area.setWidgetResizable(True); canvas=QWidget(); cl=QVBoxLayout(canvas)
        for name in ("Vocal","Drums","Bass","Music","SFX","Instrumental"):
            lane=QFrame(); lane.setObjectName("Card"); ll=QHBoxLayout(lane); ll.addWidget(QLabel(name)); clip=QPushButton("Audio clip / generated region"); clip.setMinimumWidth(420); ll.addWidget(clip); ll.addStretch(); cl.addWidget(lane)
        cl.addStretch(); area.setWidget(canvas); timel.addWidget(area)
        center.addWidget(timeline,1)

        mixer=QFrame(); mixer.setObjectName("Card"); mixer.setFixedWidth(260); ml=QVBoxLayout(mixer)
        ml.addWidget(QLabel("MIXER"))
        for name in ("Vocal","Drums","Bass","Music","Master"):
            ml.addWidget(QLabel(name)); f=QSlider(Qt.Vertical); f.setRange(0,100); f.setValue(70); f.setFixedHeight(90); ml.addWidget(f)
        ml.addStretch(); center.addWidget(mixer)
        outer.addLayout(center,1)

        transport=QHBoxLayout()
        for text in ("⏮","▶ / ⏸","■","Loop","Metronome"):
            transport.addWidget(QPushButton(text))
        transport.addWidget(QLabel("00:00 / 00:00")); transport.addStretch()
        transport.addWidget(QPushButton("Render Selection")); transport.addWidget(QPushButton("Export"))
        outer.addLayout(transport)
