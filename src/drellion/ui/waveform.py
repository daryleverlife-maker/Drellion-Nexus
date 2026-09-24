from __future__ import annotations

from pathlib import Path
import subprocess

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..audio.runtime import require_ffmpeg


class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.setAccessibleName("Selected clip waveform")
        self._peaks = np.zeros(0, dtype=np.float32)
        self._path = ""

    def clear(self):
        self._path = ""
        self._peaks = np.zeros(0, dtype=np.float32)
        self.update()

    def load_path(self, path: str, points: int = 1000):
        source = Path(path)
        if not source.is_file():
            self.clear()
            return
        if str(source) == self._path and self._peaks.size:
            return
        self._path = str(source)
        try:
            result = subprocess.run(
                [
                    require_ffmpeg(), "-v", "error", "-i", str(source),
                    "-vn", "-ac", "1", "-ar", "12000", "-f", "f32le", "pipe:1",
                ],
                capture_output=True,
                check=False,
            )
            if result.returncode:
                self.clear()
                return
            samples = np.frombuffer(result.stdout, dtype="<f4")
            if not samples.size:
                self.clear()
                return
            chunks = np.array_split(np.abs(samples), max(1, min(points, samples.size)))
            self._peaks = np.asarray([float(chunk.max()) if chunk.size else 0.0 for chunk in chunks], dtype=np.float32)
            peak = float(self._peaks.max()) if self._peaks.size else 0.0
            if peak > 0:
                self._peaks /= peak
        except Exception:
            self._peaks = np.zeros(0, dtype=np.float32)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().base())
        if not self._peaks.size:
            painter.setPen(self.palette().mid().color())
            painter.drawText(self.rect(), Qt.AlignCenter, "Select a clip to view its waveform")
            return

        pen = QPen(self.palette().highlight().color())
        pen.setWidth(1)
        painter.setPen(pen)
        width = max(1, self.width())
        height = max(1, self.height())
        middle = height / 2.0
        step = width / max(1, len(self._peaks) - 1)
        for index, value in enumerate(self._peaks):
            x = round(index * step)
            extent = float(value) * (height * 0.45)
            painter.drawLine(x, round(middle - extent), x, round(middle + extent))
