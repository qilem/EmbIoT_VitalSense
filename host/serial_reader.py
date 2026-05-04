"""
Reads newline-delimited JSON lines from the PSoC USB-CDC serial port and
pushes parsed data into AppState.

Detects legacy RAW_CAPTURE_DEBUG frames (magic 0xFFDDFFDD) and warns once,
so old firmware fails loud rather than silently producing garbage.
"""

import json
import struct
import threading
import time
import serial
from app_state import AppState

_MAGIC = 0xFFDDFFDD
_LEGACY_WARNED = False


class SerialReader:
    def __init__(self, port: str, app_state: AppState):
        self._port = port
        self._state = app_state
        self._stop = threading.Event()

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            try:
                with serial.Serial(self._port, timeout=2.0) as s:
                    self._read_loop(s)
            except serial.SerialException as e:
                print(f"[serial] {e} — retrying in 3 s")
                time.sleep(3)

    def _read_loop(self, s: serial.Serial):
        global _LEGACY_WARNED
        buf = b""
        while not self._stop.is_set():
            chunk = s.read(256)
            if not chunk:
                continue

            # Check for legacy magic header in the first bytes received
            if not _LEGACY_WARNED and len(buf) < 4:
                combined = (buf + chunk)[:4]
                if len(combined) == 4:
                    val = struct.unpack("<I", combined)[0]
                    if val == _MAGIC:
                        print(
                            "[serial] WARNING: detected RAW_CAPTURE_DEBUG firmware. "
                            "Flash the Edge-AI build (no RAW_CAPTURE_DEBUG) for JSON mode."
                        )
                        _LEGACY_WARNED = True
                        return  # bail; caller retries after 3 s

            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                self._parse(line.strip())

    def _parse(self, line: bytes):
        if not line:
            return
        try:
            data = json.loads(line.decode("ascii", errors="replace"))
            self._state.update(
                bpm=float(data.get("bpm", 0)),
                rr=float(data.get("rr", 0)),
                state=str(data.get("state", "no_signal")),
                signal=float(data.get("signal", 0)),
                target_bin=int(data.get("bin", 0)),
                present=bool(data.get("present", False)),
                timestamp_s=int(data.get("ts", 0)),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            pass  # malformed line — silently skip
