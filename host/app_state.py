"""
Thread-safe single source of truth for the latest vitals reading.
UI components read from this; SerialReader writes to this.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


HISTORY_LEN = 60  # keep 60 seconds of 1-Hz samples for sparklines


@dataclass
class VitalsSample:
    bpm: float
    rr: float
    state: str
    signal: float
    target_bin: int
    present: bool
    timestamp_s: int
    received_at: float = field(default_factory=time.monotonic)


class AppState:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest = VitalsSample(
            bpm=0, rr=0, state="no_signal", signal=0,
            target_bin=0, present=False, timestamp_s=0
        )
        self._history: Deque[VitalsSample] = deque(maxlen=HISTORY_LEN)
        self._listeners: list = []

    # ------------------------------------------------------------------ write

    def update(self, *, bpm, rr, state, signal, target_bin, present, timestamp_s):
        sample = VitalsSample(
            bpm=bpm, rr=rr, state=state, signal=signal,
            target_bin=target_bin, present=present, timestamp_s=timestamp_s
        )
        with self._lock:
            self._latest = sample
            self._history.append(sample)
        for cb in self._listeners:
            try:
                cb(sample)
            except Exception:
                pass

    # ------------------------------------------------------------------ read

    @property
    def latest(self) -> VitalsSample:
        with self._lock:
            return self._latest

    def history(self) -> list:
        with self._lock:
            return list(self._history)

    # ------------------------------------------------------------------ pub/sub

    def subscribe(self, callback):
        """Register a callable(VitalsSample) that fires on every update."""
        self._listeners.append(callback)

    def unsubscribe(self, callback):
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass
