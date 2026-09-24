from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget


class Page(QWidget):
    title = "Page"

    def __init__(self, host):
        super().__init__()
        self.host = host

    @property
    def project(self):
        return self.host.project

    def refresh(self):
        pass


class AudioTransport(QWidget):
    def __init__(self, label: str = "Player"):
        super().__init__()
        self.audio = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.8)
        self.label = QLabel(label)
        self.label.setAccessibleName(f"{label} current file")
        self.play_button = QPushButton("Play")
        self.play_button.setAccessibleName(f"Play or pause {label}")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setAccessibleName(f"Stop {label}")
        self.position = QSlider(Qt.Horizontal)
        self.position.setAccessibleName(f"{label} playback position")
        self.position.setRange(0, 0)
        row = QHBoxLayout(self)
        row.addWidget(self.play_button); row.addWidget(self.stop_button); row.addWidget(self.position, 1); row.addWidget(self.label)
        self.play_button.clicked.connect(self.toggle)
        self.stop_button.clicked.connect(self.player.stop)
        self.position.sliderMoved.connect(self.player.setPosition)
        self.player.positionChanged.connect(self.position.setValue)
        self.player.durationChanged.connect(lambda v: self.position.setRange(0, int(v)))
        self.player.playbackStateChanged.connect(self._state)

    def _state(self, state):
        self.play_button.setText("Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "Play")

    def set_path(self, path: str | Path, autoplay: bool = False):
        path = Path(path)
        if not path.exists():
            return
        self.player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.label.setText(path.name)
        if autoplay: self.player.play()

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState: self.player.pause()
        else: self.player.play()
