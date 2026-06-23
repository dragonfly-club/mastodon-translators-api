from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LRUCache[K, V]:
    def __init__(self, maxsize: int) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be positive")
        self.maxsize = maxsize
        self._data: OrderedDict[K, V] = OrderedDict()
        self._lock = Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            value = self._data.get(key)
            if value is None:
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            if len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"entries": len(self._data), "maxsize": self.maxsize}
