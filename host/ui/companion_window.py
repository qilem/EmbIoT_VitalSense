"""
Companion mode — Monika Shimeji desktop companion.

  - Three display modes: no person / aligning / detecting
  - Drag to move (shows walk animation while dragging)
  - Scroll wheel to resize
  - Critical alert: data panel flashes red
  - White-border fix: paintEvent clears to transparent via CompositionMode_Clear
"""

from __future__ import annotations
import ctypes
import sys
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QRect
from PySide6.QtGui import (QPixmap, QFont, QColor, QPainter,
                            QLinearGradient, QPaintEvent)
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QMenu

from app_state import VitalsSample
from ui.breathing_overlay import BreathingOverlay

# ──────────────────────────────────────────────────────────────────────────────
# UI Glitch Helpers (Zalgo)
# ──────────────────────────────────────────────────────────────────────────────

def zalgo_text(text: str) -> str:
    """Add minimal corruption to text for the DDLC glitch effect."""
    chars = "̷̵̴̰̹̺̻̻"
    return "".join(c + random.choice(chars) if c != " " and random.random() > 0.4 else c for c in text)

ASSETS = Path(__file__).parent.parent / "assets"

# ──────────────────────────────────────────────────────────────────────────────
# Sound system (opt-in)
# ──────────────────────────────────────────────────────────────────────────────

_sound_cache: dict[str, object] = {}

def _load_sound(filename: str, volume: float = 0.55):
    try:
        from PySide6.QtMultimedia import QSoundEffect
        from PySide6.QtCore import QUrl
        path = ASSETS / filename
        if not path.exists():
            return None
        sfx = QSoundEffect()
        sfx.setSource(QUrl.fromLocalFile(str(path)))
        sfx.setVolume(volume)
        return sfx
    except Exception:
        return None

def _play(filename: str, volume: float = 0.55, enabled: bool = True):
    if not enabled or not filename:
        return
    if filename not in _sound_cache:
        _sound_cache[filename] = _load_sound(filename, volume)
    sfx = _sound_cache[filename]
    if sfx:
        sfx.play()

# Sounds per state entry
_STATE_SOUNDS: dict[str, tuple[str, float]] = {
    "normal":      ("Nyaa_Soft.wav",    0.45),
    "stress":      ("Sigh_Sleepy.wav",  0.50),
    "critical":    ("Cartoon_Aah.wav",  0.60),
    "no_signal":   ("Hurt_Unh.wav",     0.40),
    "calibrating": ("Nyaa_Quick.wav",   0.40),
}

# Sound when bubble pops up
_BUBBLE_SOUND = ("Cartoon_Pop.wav", 0.30)

# Sound on idle check-in
_IDLE_SOUND = ("Happy_Squeals.wav", 0.35)


def _remove_win11_border(hwnd: int) -> None:
    """Disable Windows 11 DWM rounded corners that create a visible border."""
    if sys.platform != "win32":
        return
    try:
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_DONOTROUND = 1
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(ctypes.c_int(DWMWCP_DONOTROUND)),
            ctypes.sizeof(ctypes.c_int),
        )
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────────────
# Mood definitions
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Mood:
    frames:     list[str]
    frame_ms:   int
    duration_s: int = 12


_MOODS: dict[str, list[Mood]] = {
    "normal": [
        Mood(["idle1.png","idle2.png","idle3.png","idle4.png","idle5.png",
              "idle6.png","idle7.png","idle8.png","idle9.png"], 600, 12),
        Mood(["food1.png","food2.png","food3.png","food4.png"], 450, 8),
        Mood(["sit1.png","sit2.png","sit3.png","sit4.png"], 600, 10),
        Mood(["affection1.png","affection2.png","affection3.png",
              "affection4.png","affection5.png","affection6.png",
              "affection7.png","affection8.png","affection9.png"], 350, 8),
        Mood(["jump_1.png","jump_2.png","jump_3.png","jump_2.png","jump_1.png"], 200, 5),
        Mood(["sleep1.png","sleep2.png","sleep3.png","sleep2.png"], 800, 12),
    ],
    "stress": [
        Mood(["sit1.png","sit2.png","sit3.png","sit4.png"], 500, 14),
        Mood(["affection1.png","affection2.png","affection3.png","affection4.png"], 380, 10),
    ],
    "critical": [
        Mood(["hop1.png","air_swing_l.png","hop2.png","air_swing_r.png"], 120, 4),
        Mood(["jump_1.png","jump_2.png","jump_3.png","jump_2.png","hop1.png","hop2.png"], 100, 4),
        Mood(["air_swing_l.png","air_swing_r.png","hop1.png","hop2.png","air_swing_l.png"], 110, 4),
    ],
    "no_signal": [
        Mood(["sad1.png","sad2.png","sad3.png","sad4.png","sad5.png","sad6.png"], 380, 14),
        Mood(["sad2.png","sad3.png","sad4.png","sad3.png","sad2.png","sad1.png"], 420, 10),
    ],
    "calibrating": [
        Mood(["food1.png","food2.png","food3.png","food4.png","food3.png","food2.png"], 300, 10),
        Mood(["food2.png","food3.png","food4.png","food3.png","food2.png","food1.png"], 280, 8),
    ],
}

# Walk frames played while dragging
_DRAG_FRAMES = ["stand_walk1.png", "stand_walk2.png"]

_BUBBLE_COLOR: dict[str, str] = {
    "normal":      "#e8f5e9",
    "stress":      "#fff3e0",
    "critical":    "#ffebee",
    "no_signal":   "#e3f2fd",
    "calibrating": "#f3e5f5",
}

_SPRITE_SIZE_DEFAULT = 150
_SPRITE_SIZE_MIN     = 80
_SPRITE_SIZE_MAX     = 420
_SPRITE_SIZE_STEP    = 24


# ──────────────────────────────────────────────────────────────────────────────
# Inline signal bar (aim assist)
# ──────────────────────────────────────────────────────────────────────────────

class _SignalBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._signal = 0.0
        self.setFixedHeight(10)
        self.setAutoFillBackground(False)
        self.hide()

    def set_signal(self, value: float):
        self._signal = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, _: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h // 2
        p.setBrush(QColor(30, 30, 40, 140))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)
        fw = int(w * self._signal)
        if fw > 0:
            g = QLinearGradient(0, 0, w, 0)
            if self._signal < 0.4:
                g.setColorAt(0, QColor(220, 60, 60));  g.setColorAt(1, QColor(255, 130, 60))
            elif self._signal < 0.85:
                g.setColorAt(0, QColor(220, 160, 0));  g.setColorAt(1, QColor(255, 230, 0))
            else:
                g.setColorAt(0, QColor(40, 200, 90));  g.setColorAt(1, QColor(100, 255, 160))
            p.setBrush(g)
            p.drawRoundedRect(0, 0, fw, h, r, r)
        p.end()


# ──────────────────────────────────────────────────────────────────────────────
# Speech bubble
# ──────────────────────────────────────────────────────────────────────────────

class SpeechBubble(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setFont(QFont("Segoe UI", 10))
        self.setFixedWidth(280)       # fixed width forces word-wrap to activate
        self._apply_style("normal")
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def _apply_style(self, state: str):
        bg = _BUBBLE_COLOR.get(state, "#e8f5e9")
        self.setStyleSheet(
            f"background: {bg}; color: #1a1a1a;"
            " border-radius: 12px; padding: 8px 14px;"
        )

    def show_text(self, text: str, state: str, ms: int = 7000,
                  sound_enabled: bool = False):
        _play(*_BUBBLE_SOUND, enabled=sound_enabled)
        self._apply_style(state)
        self.setText(text)
        self.show()
        self._timer.start(ms)


# ──────────────────────────────────────────────────────────────────────────────
# Data panel  (shows the 3-mode status)
# ──────────────────────────────────────────────────────────────────────────────

_PANEL_NORMAL = "background: transparent; color: #e0e0e0;"
_PANEL_WARN   = "background: transparent; color: #ffcc44;"
_PANEL_ALERT  = "background: transparent; color: #ff4444;"

class DataPanel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setStyleSheet(_PANEL_NORMAL)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setText("Sit in front of the sensor")
        self._glitch_active = False

    def set_glitch(self, active: bool):
        self._glitch_active = active

    def refresh(self, sample: VitalsSample):
        state = sample.state
        if state == "no_signal":
            self.setStyleSheet(_PANEL_NORMAL)
            self.setText("No one detected")
        elif state == "calibrating":
            self.setStyleSheet(_PANEL_WARN)
            self.setText("Detecting...")
        else:
            bpm_val = f"{sample.bpm:.0f}" if sample.bpm > 0 else "--"
            rr_val  = f"{sample.rr:.0f}"  if sample.rr  > 0 else "--"
            
            text = f"♥ {bpm_val} BPM   {rr_val}/min"
            if self._glitch_active:
                text = zalgo_text(text)

            if state == "stress":
                self.setStyleSheet(_PANEL_WARN)
            elif state != "critical":
                self.setStyleSheet(_PANEL_NORMAL)
            self.setText(text)

    def set_flash(self, on: bool):
        self.setStyleSheet(_PANEL_ALERT if on else _PANEL_NORMAL)


# ──────────────────────────────────────────────────────────────────────────────
# Main companion window
# ──────────────────────────────────────────────────────────────────────────────

class CompanionWindow(QWidget):
    breathing_exercise_requested = Signal()

    def __init__(self, dialogue_fn: Callable, settings_fn: Callable | None = None,
                 settings=None):
        super().__init__()
        self._dialogue_fn   = dialogue_fn
        self._settings_fn   = settings_fn
        self._settings      = settings

        self._current_state = "calibrating"
        self._mood_list:  list[Mood] = []
        self._mood_idx:   int        = 0
        self._frames:     list[QPixmap] = []
        self._frame_idx:  int        = 0
        self._sprite_size: int       = _SPRITE_SIZE_DEFAULT
        self._base_sprite_size: int  = _SPRITE_SIZE_DEFAULT
        self._base_pos:    QPoint | None = None

        self._drag_origin: QPoint | None = None
        self._drag_moved   = False
        self._dragging     = False

        self._pending_state: str = "calibrating"
        self._pending_count: int = 0

        self._setup_window()
        self._build_ui()

        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._next_frame)

        self._mood_timer = QTimer(self)
        self._mood_timer.setSingleShot(True)
        self._mood_timer.timeout.connect(self._next_mood)

        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(20_000)
        self._idle_timer.timeout.connect(self._idle_bubble)
        self._idle_timer.start()

        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(500)
        self._flash_timer.timeout.connect(self._flash_tick)
        self._flash_state = False

        self._shake_timer = QTimer(self)
        self._shake_timer.setInterval(40)
        self._shake_timer.timeout.connect(self._shake_tick)

        self._glitch_timer = QTimer(self)
        self._glitch_timer.setSingleShot(True)
        self._glitch_timer.timeout.connect(self._stop_glitch)

        self._breathing_overlay: BreathingOverlay | None = None
        self._breathing_active = False

        self._enter_state("calibrating")

    @property
    def _sound_enabled(self) -> bool:
        return bool(self._settings and self._settings.sound_enabled)

    # ── window setup ──────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAutoFillBackground(False)
        self._snap_to_corner()

    def showEvent(self, event):
        super().showEvent(event)
        _remove_win11_border(int(self.winId()))

    def _snap_to_corner(self):
        self._refit()
        sc = QApplication.primaryScreen().availableGeometry()
        self.move(sc.right() - self.width() - 20,
                  sc.bottom() - self.height() - 20)

    def _refit(self):
        s = self._sprite_size
        self.resize(max(s + 60, 280), s + 120)
        self._sprite_label.setFixedSize(s, s)

    # definitive white-border fix: clear all pixels to transparent
    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.end()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(3)

        self._bubble = SpeechBubble(self)
        layout.addWidget(self._bubble, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._sprite_label = QLabel(self)
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sprite_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._sprite_label.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._sprite_label.setAutoFillBackground(False)
        self._sprite_label.setStyleSheet("background: transparent; border: none;")
        self._sprite_label.setFixedSize(self._sprite_size, self._sprite_size)
        layout.addWidget(self._sprite_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._signal_bar = _SignalBar(self)
        layout.addWidget(self._signal_bar)

        self._data_panel = DataPanel(self)
        layout.addWidget(self._data_panel, alignment=Qt.AlignmentFlag.AlignHCenter)

    # ── state & mood machine ──────────────────────────────────────────────────

    def _enter_state(self, state: str):
        self._bubble.hide()  # clear any lingering bubble from the previous state
        
        # Transitions
        old_state = self._current_state
        self._current_state = state

        if state == "critical":
            if old_state != "critical":
                # Save state for restoration
                self._base_pos = self.pos()
                self._base_sprite_size = self._sprite_size
                # Double size
                self._sprite_size = min(_SPRITE_SIZE_MAX, self._sprite_size * 2)
                self._refit()
                # Center
                sc = QApplication.primaryScreen().availableGeometry()
                self.move(sc.center().x() - self.width() // 2,
                          sc.center().y() - self.height() // 2)
                self._shake_timer.start()
        elif old_state == "critical":
            # Restore from critical
            self._shake_timer.stop()
            self._sprite_size = self._base_sprite_size
            self._refit()
            if self._base_pos:
                self.move(self._base_pos)

        if state == "stress":
            self._data_panel.set_glitch(True)
            self._glitch_timer.start(2500)
            self._start_breathing()
        else:
            self._stop_breathing()

        self._mood_list = _MOODS.get(state, _MOODS["normal"])
        self._mood_idx  = 0
        self._start_mood(self._mood_list[0])
        
        if state in _STATE_SOUNDS:
            snd, vol = _STATE_SOUNDS[state]
            _play(snd, vol, self._sound_enabled)
        
        # start/stop critical flash
        if state == "critical":
            self._flash_state = False
            self._flash_timer.start()
        else:
            self._flash_timer.stop()
            self._flash_state = False

    def _start_mood(self, mood: Mood):
        self._load_frames(mood.frames, mood.frame_ms)
        self._mood_timer.start(mood.duration_s * 1000)

    def _next_mood(self):
        if self._dragging:
            return  # don't rotate moods while being dragged
        self._mood_idx = (self._mood_idx + 1) % len(self._mood_list)
        self._start_mood(self._mood_list[self._mood_idx])

    # ── frame loading & animation ─────────────────────────────────────────────

    def _load_frames(self, filenames: list[str], interval_ms: int):
        s = self._sprite_size
        pixmaps = []
        for fname in filenames:
            p = ASSETS / fname
            if p.exists():
                pix = QPixmap(str(p))
                if not pix.isNull():
                    pixmaps.append(
                        pix.scaled(s, s,
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                    )
        if not pixmaps:
            blank = QPixmap(s, s)
            blank.fill(QColor(0, 0, 0, 0))
            pixmaps = [blank]
        self._frames    = pixmaps
        self._frame_idx = 0
        self._sprite_label.setPixmap(self._frames[0])
        self._frame_timer.start(interval_ms)

    def _next_frame(self):
        if self._frames:
            self._frame_idx = (self._frame_idx + 1) % len(self._frames)
            self._sprite_label.setPixmap(self._frames[self._frame_idx])

    # ── public update (4 Hz from main thread) ─────────────────────────────────

    def on_state_update(self, sample: VitalsSample):
        self._data_panel.refresh(sample)

        new_state = sample.state
        if new_state == self._pending_state:
            self._pending_count += 1
        else:
            self._pending_state = new_state
            self._pending_count = 1

        # Require 3 consecutive matching samples (~750 ms) before committing a
        # state change so brief signal drops don't trigger sad animations or
        # the "can't sense you" dialogue while the user is present.
        if (self._pending_count >= 3
                and new_state != self._current_state
                and not self._dragging):
            self._enter_state(new_state)
            self._show_dialogue(new_state, sample.bpm, sample.rr)

        if self._current_state in ("no_signal", "calibrating"):
            self._signal_bar.set_signal(sample.signal)
            self._signal_bar.show()
        else:
            self._signal_bar.hide()
        
        # Biofeedback check: if breathing is healthy during stress, we can transition back
        if self._breathing_active and sample.rr > 0 and sample.rr < 16:
            # Successfully relaxed
            self._stop_breathing()
            self._bubble.show_text("That's the spirit! Just relax a little.", "normal", 
                                   sound_enabled=self._sound_enabled)

    def _show_dialogue(self, state: str, bpm: float, rr: float):
        se = self._sound_enabled

        def _on_llm_ready(text: str):
            if self._current_state == state:
                QTimer.singleShot(0, lambda: self._bubble.show_text(text, state, sound_enabled=se))

        try:
            line = self._dialogue_fn(state, bpm, rr, callback=_on_llm_ready)
        except TypeError:
            line = self._dialogue_fn(state, bpm, rr)
        
        # Custom dialogue overrides for new features
        if state == "stress":
            line = "Your breathing is all over the place. Look into my eyes and take a deep breath, following this rhythm."
        elif state == "critical":
            line = f"Stop what you're doing. Your heart rate is {bpm:.0f}; you need to get out of your seat and walk around."

        self._bubble.show_text(line, state, sound_enabled=se)

    def _idle_bubble(self):
        if self._current_state == "normal" and not self._dragging:
            _play(*_IDLE_SOUND, enabled=self._sound_enabled)
            self._show_dialogue("normal", 0, 0)

    # ── special effects ───────────────────────────────────────────────────────

    def _shake_tick(self):
        if self._current_state != "critical" or self._dragging:
            return
        dx = random.randint(-4, 4)
        dy = random.randint(-4, 4)
        center = QApplication.primaryScreen().availableGeometry().center()
        self.move(center.x() - self.width() // 2 + dx,
                  center.y() - self.height() // 2 + dy)

    def _stop_glitch(self):
        self._data_panel.set_glitch(False)

    def _start_breathing(self):
        if not self._breathing_overlay:
            self._breathing_overlay = BreathingOverlay()
        self._breathing_overlay.show()
        self._breathing_overlay.start()
        self._breathing_active = True

    def _stop_breathing(self):
        if self._breathing_overlay:
            self._breathing_overlay.hide()
        self._breathing_active = False

    # ── critical flash ────────────────────────────────────────────────────────

    def _flash_tick(self):
        self._flash_state = not self._flash_state
        self._data_panel.set_flash(self._flash_state)

    # ── drag to move (shows walk animation) ───────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._current_state == "critical":
                # Clicking dismisses critical interruption
                self._enter_state("normal")
                return
            self._drag_origin = event.globalPosition().toPoint()
            self._drag_moved  = False

    def mouseMoveEvent(self, event):
        if self._drag_origin and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_origin
            if delta.manhattanLength() > 5 and not self._drag_moved:
                self._drag_moved = True
                self._dragging   = True
                self._mood_timer.stop()
                self._load_frames(_DRAG_FRAMES, 150)
            if self._drag_moved:
                self.move(self.pos() + delta)
                self._drag_origin = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._dragging
            self._drag_origin = None
            self._drag_moved  = False
            self._dragging    = False
            if was_dragging:
                self._enter_state(self._current_state)
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        if self._settings_fn:
            menu.addAction("Settings…").triggered.connect(self._settings_fn)
        menu.addSeparator()
        menu.addAction("Quit").triggered.connect(QApplication.quit)
        menu.exec(pos)

    # ── scroll to resize ──────────────────────────────────────────────────────

    def wheelEvent(self, event):
        step = _SPRITE_SIZE_STEP if event.angleDelta().y() > 0 else -_SPRITE_SIZE_STEP
        new_sz = max(_SPRITE_SIZE_MIN, min(_SPRITE_SIZE_MAX, self._sprite_size + step))
        if new_sz == self._sprite_size:
            return
        self._sprite_size = new_sz
        self._sprite_label.setFixedSize(new_sz, new_sz)
        self._refit()
        mood = self._mood_list[self._mood_idx]
        self._load_frames(mood.frames, mood.frame_ms)
