"""
Minimalist "pill" mode: semi-transparent dark bar at the top of the screen.
Shows heart rate + RR + a color-coded status dot.
Shakes on critical state.
"""

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve, QRect
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QApplication

from app_state import VitalsSample

_STATE_COLORS = {
    "normal":      "rgba(20,20,30,160)",
    "stress":      "rgba(180,90,0,200)",
    "critical":    "rgba(180,0,0,220)",
    "no_signal":   "rgba(20,20,30,100)",
    "calibrating": "rgba(20,20,30,100)",
}

_STATE_TEXT_COLORS = {
    "normal":      "#b0f0b0",
    "stress":      "#ffe0a0",
    "critical":    "#ffb0b0",
    "no_signal":   "#808090",
    "calibrating": "#808090",
}


class PillWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._current_state = "calibrating"
        self._setup_window()
        self._build_ui()
        self._shake_anim = None

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._position_top_center()

    def _position_top_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = 260, 36
        self.setFixedSize(w, h)
        self.move(screen.center().x() - w // 2, screen.top() + 4)

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(12)

        self._label = QLabel("  --  |  --")
        self._label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._apply_style("calibrating")

    def _apply_style(self, state: str):
        bg    = _STATE_COLORS.get(state, _STATE_COLORS["normal"])
        color = _STATE_TEXT_COLORS.get(state, "#b0f0b0")
        self.setStyleSheet(
            f"QWidget {{ background: {bg}; border-radius: 18px; }}"
        )
        self._label.setStyleSheet(f"QLabel {{ color: {color}; background: transparent; }}")

    def on_state_update(self, sample: VitalsSample):
        if not sample.present:
            self._label.setText("  --  |  --")
        else:
            bpm = f"{sample.bpm:.0f}" if sample.bpm > 0 else "--"
            rr  = f"{sample.rr:.0f}"  if sample.rr  > 0 else "--"
            self._label.setText(f"♥ {bpm}  |  \U0001f4a8 {rr}/min")

        if sample.state != self._current_state:
            self._current_state = sample.state
            self._apply_style(sample.state)
            if sample.state == "critical":
                self._shake()

    def _shake(self):
        if self._shake_anim and self._shake_anim.state() == QPropertyAnimation.State.Running:
            return
        pos = self.pos()
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(400)
        anim.setLoopCount(3)
        anim.setKeyValueAt(0.0, pos)
        anim.setKeyValueAt(0.2, QPoint(pos.x() - 8, pos.y()))
        anim.setKeyValueAt(0.4, QPoint(pos.x() + 8, pos.y()))
        anim.setKeyValueAt(0.6, QPoint(pos.x() - 6, pos.y()))
        anim.setKeyValueAt(0.8, QPoint(pos.x() + 6, pos.y()))
        anim.setKeyValueAt(1.0, pos)
        anim.setEasingCurve(QEasingCurve.Type.Linear)
        self._shake_anim = anim
        anim.start()
