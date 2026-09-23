from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

@dataclass
class HistoryEntry(Generic[T]):
    label: str
    state: T

class History(Generic[T]):
    def __init__(self, initial: T, limit: int = 100) -> None:
        self.limit = max(2, limit)
        self._undo = [HistoryEntry("Initial", deepcopy(initial))]
        self._redo = []

    def push(self, label: str, state: T) -> None:
        self._undo.append(HistoryEntry(label, deepcopy(state)))
        self._undo = self._undo[-self.limit:]
        self._redo.clear()

    def undo(self):
        if len(self._undo) <= 1:
            return None
        self._redo.append(self._undo.pop())
        return deepcopy(self._undo[-1].state)

    def redo(self):
        if not self._redo:
            return None
        item = self._redo.pop()
        self._undo.append(item)
        return deepcopy(item.state)

    def labels(self):
        return [item.label for item in self._undo]
