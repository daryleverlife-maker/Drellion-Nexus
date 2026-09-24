from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn, *args, inject_progress: bool = True, **kwargs):
        super().__init__()
        self.fn = fn; self.args = args; self.kwargs = kwargs; self.inject_progress = inject_progress
        self.signals = WorkerSignals(); self.cancel_requested = False

    def cancel(self): self.cancel_requested = True

    def _progress(self, message: str):
        if self.cancel_requested: raise RuntimeError("Cancelled")
        self.signals.progress.emit(message)

    @Slot()
    def run(self):
        try:
            if self.inject_progress and "progress" not in self.kwargs: self.kwargs["progress"] = self._progress
            result = self.fn(*self.args, **self.kwargs)
            if self.cancel_requested: raise RuntimeError("Cancelled")
        except Exception as exc: self.signals.error.emit(str(exc))
        else: self.signals.finished.emit(result)
