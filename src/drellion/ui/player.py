from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
)


def _clock(ms: int) -> str:
    total = max(0, int(ms // 1000))
    return f"{total // 60:02d}:{total % 60:02d}"


class PlayerBar(QFrame):
    """Persistent project player for vocal/reference/preview/build/master auditioning."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._sources: dict[str, str] = {}
        self._duration = 0
        self._seeking = False

        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.8)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        layout.addWidget(QLabel("PLAYER"))

        self.source = QComboBox()
        self.source.setMinimumWidth(190)
        self.source.currentTextChanged.connect(self._source_changed)
        layout.addWidget(self.source)

        back = QPushButton("−5s")
        back.clicked.connect(lambda: self.player.setPosition(max(0, self.player.position() - 5000)))
        layout.addWidget(back)

        self.play = QPushButton("▶")
        self.play.clicked.connect(self._toggle_play)
        layout.addWidget(self.play)

        stop = QPushButton("■")
        stop.clicked.connect(self.player.stop)
        layout.addWidget(stop)

        forward = QPushButton("+5s")
        forward.clicked.connect(
            lambda: self.player.setPosition(
                min(self._duration or self.player.position() + 5000, self.player.position() + 5000)
            )
        )
        layout.addWidget(forward)

        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.sliderPressed.connect(self._seek_pressed)
        self.seek.sliderReleased.connect(self._seek_released)
        layout.addWidget(self.seek, 1)

        self.time = QLabel("00:00 / 00:00")
        self.time.setMinimumWidth(105)
        layout.addWidget(self.time)

        layout.addWidget(QLabel("Vol"))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        self.volume.setMaximumWidth(100)
        self.volume.valueChanged.connect(lambda value: self.audio.setVolume(value / 100.0))
        layout.addWidget(self.volume)

        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.playbackStateChanged.connect(self._state_changed)

    def set_sources(self, sources: dict[str, str], preferred: str | None = None) -> None:
        current = preferred or self.source.currentText()
        self._sources = {label: path for label, path in sources.items() if path}
        self.source.blockSignals(True)
        self.source.clear()
        self.source.addItems(self._sources.keys())
        if current in self._sources:
            self.source.setCurrentText(current)
        self.source.blockSignals(False)
        if self.source.currentText():
            self._source_changed(self.source.currentText())

    def load_path(self, path: str, label: str = "Current") -> None:
        if not path:
            return
        self._sources[label] = path
        self.set_sources(self._sources, preferred=label)

    def _source_changed(self, label: str) -> None:
        path = self._sources.get(label, "")
        if not path:
            return
        source = Path(path)
        if source.is_file():
            self.player.setSource(QUrl.fromLocalFile(str(source.resolve())))

    def _toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _seek_pressed(self) -> None:
        self._seeking = True

    def _seek_released(self) -> None:
        self._seeking = False
        if self._duration:
            self.player.setPosition(round(self.seek.value() / 1000.0 * self._duration))

    def _position_changed(self, position: int) -> None:
        if self._duration and not self._seeking:
            self.seek.setValue(round(position / self._duration * 1000))
        self.time.setText(f"{_clock(position)} / {_clock(self._duration)}")

    def _duration_changed(self, duration: int) -> None:
        self._duration = max(0, duration)
        self._position_changed(self.player.position())

    def _state_changed(self, state) -> None:
        self.play.setText("⏸" if state == QMediaPlayer.PlayingState else "▶")
