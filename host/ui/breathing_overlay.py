"""
Guided breathing overlay: pulsing halo + phase text (Inhale / Exhale).
Triggered by clicking Vita during stress/critical state.
"""

import math
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication

_INHALE_MS  = 4000
_EXHALE_MS  = 6000
_CYCLE_MS   = _INHALE_MS + _EXHALE_MS
_TOTAL_CYCLES = 5


class BreathingOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(320, 320)
        self._center_on_screen()

        self._elapsed_ms = 0
        self._cycles_done = 0
        self._radius_frac = 0.5  # 0..1

        self._tick = QTimer(self)
        self._tick.setInterval(30)
        self._tick.timeout.connect(self._advance)

        self._build_ui()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2,
                  screen.center().y() - self.height() // 2)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 200, 0, 0)

        self._phase_label = QLabel("Inhale...")
        self._phase_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._phase_label.setStyleSheet("QLabel { color: #ffffff; background: transparent; }")
        layout.addWidget(self._phase_label)

        self._close_label = QLabel("(click to close)")
        self._close_label.setFont(QFont("Segoe UI", 9))
        self._close_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._close_label.setStyleSheet("QLabel { color: rgba(255,255,255,120); background: transparent; }")
        layout.addWidget(self._close_label)

    def start(self):
        self._elapsed_ms = 0
        self._cycles_done = 0
        self._tick.start()

    def _advance(self):
        self._elapsed_ms += 30
        pos_in_cycle = self._elapsed_ms % _CYCLE_MS

        if pos_in_cycle < _INHALE_MS:
            t = pos_in_cycle / _INHALE_MS
            self._radius_frac = 0.35 + 0.45 * t
            self._phase_label.setText("Inhale...")
        else:
            t = (pos_in_cycle - _INHALE_MS) / _EXHALE_MS
            self._radius_frac = 0.8 - 0.45 * t
            self._phase_label.setText("Exhale...")

        if self._elapsed_ms // _CYCLE_MS > self._cycles_done:
            self._cycles_done += 1
            if self._cycles_done >= _TOTAL_CYCLES:
                self._tick.stop()
                self.hide()
                return

        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() // 2, self.height() // 2
        r = int(self._radius_frac * min(cx, cy))

        grad = QRadialGradient(cx, cy, r)
        grad.setColorAt(0.0, QColor(100, 200, 255, 160))
        grad.setColorAt(0.7, QColor(60,  120, 255, 80))
        grad.setColorAt(1.0, QColor(30,   60, 180, 0))

        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - r, cy - r, 2*r, 2*r)
        p.end()

    def mousePressEvent(self, event):
        self._tick.stop()
        self.hide()
