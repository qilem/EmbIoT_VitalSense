"""Settings dialog reachable from the tray icon."""

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QDialogButtonBox, QLabel
)
from PySide6.QtCore import Qt
from settings import Settings


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Vita — Settings")
        self.setMinimumWidth(380)
        self._build_ui()

    def _build_ui(self):
        form = QFormLayout(self)

        self._port = QLineEdit(self._settings.serial_port)
        self._port.setPlaceholderText("e.g. COM3 or /dev/tty.usbmodem2439")
        form.addRow("Serial port:", self._port)

        self._provider = QComboBox()
        self._provider.addItems(["", "anthropic", "openai"])
        idx = self._provider.findText(self._settings.api_provider)
        if idx >= 0:
            self._provider.setCurrentIndex(idx)
        form.addRow("LLM provider:", self._provider)

        self._key = QLineEdit(self._settings.api_key)
        self._key.setEchoMode(QLineEdit.EchoMode.Password)
        self._key.setPlaceholderText("Paste API key (stored in ~/.vita/settings.json)")
        form.addRow("API key:", self._key)

        note = QLabel(
            "The API key is stored in plain text in ~/.vita/settings.json.\n"
            "Leave blank to use offline canned dialogue."
        )
        note.setStyleSheet("color: gray; font-size: 9pt;")
        note.setWordWrap(True)
        form.addRow("", note)

        self._sound = QCheckBox("Enable sound effects")
        self._sound.setChecked(self._settings.sound_enabled)
        form.addRow("", self._sound)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _save(self):
        self._settings.serial_port = self._port.text().strip()
        self._settings.set("api_provider", self._provider.currentText())
        self._settings.set("api_key", self._key.text().strip())
        self._settings.sound_enabled = self._sound.isChecked()
        self.accept()
