"""
PC-DSP fallback mode.

Reads the original RAW_CAPTURE_DEBUG binary stream from the board
(magic-framed uint16 chunks), runs the Python Pipeline DSP on the PC,
and pushes VitalsSample updates into AppState — identical interface to
SerialReader so main.py doesn't care which path is active.

Use this when the CM4 has insufficient RAM for the on-device DSP.
The firmware can be flashed with RAW_CAPTURE_DEBUG defined (or just left
as the original main.c that always streams raw data).
"""

import struct
import threading
import time
import numpy as np
import serial

from pipeline import Pipeline
from app_state import AppState

MAGIC = 0xFFDDFFDD
SAMPLE_PER_CHIRP = 128
CHIRP_PER_FRAME  = 256

# Presence floor: mean |spec| peak > this → person detected.
# 200k was observed as a clear-presence marker; use half that as the detection floor
# so the sensor catches the person reliably before the strong-lock threshold.
_PRESENCE_FLOOR = 100_000.0


def _peak_energy(mag: np.ndarray) -> float:
    return float(mag[5:].max()) if len(mag) > 5 else 0.0


def _zero_crossing_bpm(sig: np.ndarray, fs: float) -> float:
    crossings = int(np.sum((sig[:-1] < 0) != (sig[1:] < 0)))
    cycles = crossings / 2.0
    duration_s = len(sig) / fs
    bpm = (cycles / duration_s) * 60.0
    return bpm if 4 <= bpm <= 300 else 0.0


class PcDspReader:
    def __init__(self, port: str, app_state: AppState):
        self._port = port
        self._state = app_state
        self._stop = threading.Event()
        self._pipe = Pipeline(
            SAMPLE_PER_CHIRP,
            buffer_size=CHIRP_PER_FRAME * 32,
            window_size=CHIRP_PER_FRAME * 8,
            stride=64,
        )
        self._peak_energy_seen = 1.0
        self._frames_ready = 0          # count of processed frames (calibrating gate)
        self._bpm_baseline = 0.0        # 5-min EMA baseline for stress detection
        self._elevated_since: float | None = None  # monotonic time when BPM went high
        self._no_signal_since: float | None = None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            try:
                with serial.Serial(self._port, timeout=2.0) as s:
                    self._read_loop(s)
            except serial.SerialException as e:
                print(f"[pc_dsp] {e} — retrying in 3 s")
                time.sleep(3)

    def _read_loop(self, s: serial.Serial):
        self._sync(s)
        while not self._stop.is_set():
            raw = s.read(4)
            if len(raw) < 4:
                continue
            nbytes = struct.unpack("<I", raw)[0]
            data_raw = s.read(nbytes)
            samples = [d[0] for d in struct.iter_unpack("<H", data_raw)]

            self._pipe.enque(samples)
            if self._pipe.data_ready():
                self._process()

            peek = s.read(4)
            if len(peek) < 4 or struct.unpack("<I", peek)[0] != MAGIC:
                self._sync(s)

    def _process(self):
        mag = np.abs(self._pipe.range_fft()).mean(axis=0)
        breath, heart = self._pipe.vitals()

        energy = _peak_energy(mag)
        if energy > self._peak_energy_seen:
            self._peak_energy_seen = energy
        signal_norm = min(1.0, energy / self._peak_energy_seen) if self._peak_energy_seen > 0 else 0.0
        present = energy > _PRESENCE_FLOOR

        fs = self._pipe._fs
        bpm = _zero_crossing_bpm(heart,  fs) if present else 0.0
        rr  = _zero_crossing_bpm(breath, fs) if present else 0.0

        # Clamp to physiological ranges
        bpm = bpm if 30 <= bpm <= 200 else 0.0
        rr  = rr  if  4 <= rr  <=  40 else 0.0

        self._frames_ready += 1
        now = time.monotonic()

        # Derive state — 3 modes:
        #   calibrating : pipeline warming up (first 5 frames)
        #   no_signal   : no person, OR person present but both bpm+rr dropped to 0 (lost signal)
        #   normal/stress/critical : full detection
        if self._frames_ready < 5:
            state = "calibrating"
        elif not present or bpm == 0:
            # No one detected — always calm no_signal, never alert
            self._elevated_since = None
            self._no_signal_since = None
            state = "no_signal"
        else:
            # Person present with valid BPM — run stress/critical logic
            self._no_signal_since = None
            if self._bpm_baseline == 0.0:
                self._bpm_baseline = bpm
            else:
                self._bpm_baseline += 0.001 * (bpm - self._bpm_baseline)

            elevated = (bpm - self._bpm_baseline) > 20
            if elevated:
                if self._elevated_since is None:
                    self._elevated_since = now
                elapsed = now - self._elevated_since
                state = "critical" if elapsed > 120 else "stress" if elapsed > 30 else "normal"
            else:
                self._elevated_since = None
                state = "normal"

        self._state.update(
            bpm=bpm, rr=rr, state=state,
            signal=signal_norm, target_bin=0,
            present=present, timestamp_s=int(time.time()),
        )

    def _sync(self, s: serial.Serial):
        buf = b""
        while True:
            buf = (buf + s.read(1))[-4:]
            if len(buf) == 4 and struct.unpack("<I", buf)[0] == MAGIC:
                return
