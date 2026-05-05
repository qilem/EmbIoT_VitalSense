"""
Vita Desktop Companion — entry point.

Bootstraps QApplication, tray icon, serial reader, and the active UI mode
(companion or pill).  All UI updates are driven by a QTimer polling AppState
on the main thread so Qt widget access is always single-threaded.

DSP modes (set via --dsp or settings.json "dsp_mode"):
  "edge"   — firmware sends JSON lines (default, requires edge-AI firmware)
  "pc"     — firmware sends raw MAGIC stream; DSP runs here via pipeline.py
  "demo"   — no hardware; cycles through fake states for UI testing
"""

import sys
import signal
import argparse
import itertools
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox

from settings import Settings
from app_state import AppState
from dialogue.canned import get_line as canned_line
from ui.companion_window import CompanionWindow
from ui.pill_window import PillWindow
from ui.settings_dialog import SettingsDialog

ASSETS = Path(__file__).parent / "assets"

# Demo mode: cycle through these states every N seconds
_DEMO_STATES = itertools.cycle([
    dict(bpm=72,  rr=15, state="calibrating", signal=0.1,  present=False),
    dict(bpm=72,  rr=15, state="no_signal",   signal=0.3,  present=False),
    dict(bpm=72,  rr=15, state="no_signal",   signal=0.7,  present=False),
    dict(bpm=72,  rr=15, state="normal",      signal=0.92, present=True),
    dict(bpm=72,  rr=15, state="normal",      signal=0.95, present=True),
    dict(bpm=98,  rr=22, state="stress",      signal=0.91, present=True),
    dict(bpm=0,   rr=0,  state="critical",    signal=0.04, present=False),
])
_DEMO_INTERVAL_MS = 3000


def _make_tray_icon() -> QIcon:
    icon_path = ASSETS / "tray_icon.png"
    if icon_path.exists():
        return QIcon(str(icon_path))
    pix = QPixmap(32, 32)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(80, 200, 120))
    p.setPen(QColor(40, 140, 80))
    p.drawEllipse(4, 4, 24, 24)
    p.end()
    return QIcon(pix)


def _build_dialogue_fn(settings: Settings):
    if settings.has_llm():
        from dialogue.llm_client import LLMClient
        client = LLMClient(settings.api_provider, settings.api_key)
        return client.get_line
    return lambda state, bpm, rr: canned_line(state)


def _start_reader(dsp_mode: str, port: str, app_state: AppState):
    def _on_port_error(msg: str):
        from PySide6.QtCore import QTimer as _QTimer
        from PySide6.QtWidgets import QApplication as _QApp, QMessageBox as _QMB
        
        # Update state so Monika says something
        app_state.update(
            bpm=0, rr=0, state="disconnected", signal=0,
            target_bin=0, present=False, timestamp_s=int(time.time())
        )

        def _show():
            box = _QMB()
            box.setWindowTitle("Vita — Serial Port Error")
            box.setIcon(_QMB.Icon.Critical)
            box.setText(
                f"Could not open serial port <b>{port}</b>.<br><br>"
                f"<i>{msg}</i><br><br>"
                "1. Confirm both USB-C cables are connected.<br>"
                "2. Check <b>Settings</b> in the tray icon to verify the port name.<br>"
                "3. Close any other apps using this port.<br><br>"
                "The app will continue retrying in the background."
            )
            box.setStandardButtons(_QMB.StandardButton.Ok)
            box.exec()
        
        instance = _QApp.instance()
        if instance:
            _QTimer.singleShot(0, instance, _show)
        else:
            print(f"Error: {msg}")

    if dsp_mode == "pc":
        from pc_dsp_reader import PcDspReader
        r = PcDspReader(port, app_state, on_error=_on_port_error)
    else:
        from serial_reader import SerialReader
        r = SerialReader(port, app_state, on_error=_on_port_error)
    r.start()
    return r


def _start_demo(app_state: AppState) -> QTimer:
    timer = QTimer()
    timer.setInterval(_DEMO_INTERVAL_MS)

    def _tick():
        d = next(_DEMO_STATES)
        app_state.update(
            bpm=d["bpm"], rr=d["rr"], state=d["state"],
            signal=d["signal"], target_bin=12,
            present=d["present"], timestamp_s=int(time.time()),
        )

    _tick()  # fire immediately so the UI isn't blank at startup
    timer.timeout.connect(_tick)
    timer.start()
    return timer


def main():
    # Allow --dsp flag to override settings (useful for quick testing)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dsp", choices=["edge", "pc", "demo"], default=None)
    parser.add_argument("--serial", default=None)
    args, _ = parser.parse_known_args()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Let Ctrl+C kill the app even while Qt is running
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    _sigint_timer = QTimer()
    _sigint_timer.setInterval(200)
    _sigint_timer.timeout.connect(lambda: None)  # wake event loop so signal is delivered
    _sigint_timer.start()

    settings = Settings()

    dsp_mode = args.dsp or settings.get("dsp_mode", "edge")
    port = args.serial or settings.serial_port

    if dsp_mode != "demo" and not port:
        msg = QMessageBox()
        msg.setWindowTitle("Vita — First Run")
        msg.setText(
            "No serial port configured.\n\n"
            "Open Settings from the tray icon and enter your device port\n"
            "(e.g. COM3 on Windows, /dev/tty.usbmodem2439 on macOS),\n\n"
            "or launch with --dsp demo to test the UI without hardware."
        )
        msg.exec()

    app_state = AppState()
    dialogue_fn = _build_dialogue_fn(settings)

    companion = CompanionWindow(
        dialogue_fn,
        settings_fn=lambda: _open_settings(settings),
        settings=settings,
    )
    pill = PillWindow()

    def _show_mode(mode: str):
        settings.mode = mode
        if mode == "companion":
            pill.hide()
            companion.show()
        else:
            companion.hide()
            pill.show()

    if settings.mode == "companion":
        companion.show()
    else:
        pill.show()

    # Tray icon
    tray = QSystemTrayIcon(_make_tray_icon(), app)
    tray.setToolTip("Vita — Vital Sense Companion")
    menu = QMenu()

    dsp_label = f"DSP: {dsp_mode}"
    menu.addAction(dsp_label).setEnabled(False)
    menu.addSeparator()

    act_companion = menu.addAction("Companion mode")
    act_companion.triggered.connect(lambda: _show_mode("companion"))
    act_pill = menu.addAction("Minimalist (pill) mode")
    act_pill.triggered.connect(lambda: _show_mode("pill"))
    menu.addSeparator()
    act_settings = menu.addAction("Settings...")
    act_settings.triggered.connect(lambda: _open_settings(settings))
    menu.addSeparator()
    act_quit = menu.addAction("Quit")
    act_quit.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    tray.show()

    # Start data source
    _demo_timer = None
    _reader = None
    if dsp_mode == "demo":
        _demo_timer = _start_demo(app_state)
    elif port:
        _reader = _start_reader(dsp_mode, port, app_state)

    # UI refresh at 4 Hz on main thread
    def _refresh():
        sample = app_state.latest
        companion.on_state_update(sample)
        pill.on_state_update(sample)

    refresh_timer = QTimer()
    refresh_timer.setInterval(250)
    refresh_timer.timeout.connect(_refresh)
    refresh_timer.start()

    sys.exit(app.exec())


def _open_settings(settings: Settings):
    dlg = SettingsDialog(settings)
    dlg.exec()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
