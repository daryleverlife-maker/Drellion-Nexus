from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal


class FunctionThread(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, function: Callable, *args, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.function(*self.args, **self.kwargs)
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(result)
