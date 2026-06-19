"""
ui/settings_panel.py — File upload controls and audio device selector.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFileDialog
)
from PyQt6.QtCore import Qt
import os

BG_CARD  = "#1a1a1d"
TEXT     = "#e8e8ea"
TEXT_DIM = "#6b6b75"
SUCCESS  = "#3dd68c"
WARNING  = "#f5a623"
BORDER   = "#2a2a2e"
ACCENT   = "#4f8ef7"


class SettingsPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cv_path   = ""
        self._tone_path = ""
        self._build_ui()
        self._populate_devices()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # CV row
        cv_row = QHBoxLayout()
        self._cv_label = QLabel("CV: not loaded")
        self._cv_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        btn_cv = QPushButton("Browse…")
        btn_cv.setFixedWidth(80)
        btn_cv.clicked.connect(self._pick_cv)
        cv_row.addWidget(QLabel("📄"))
        cv_row.addWidget(self._cv_label, stretch=1)
        cv_row.addWidget(btn_cv)
        layout.addLayout(cv_row)

        # Tone row
        tone_row = QHBoxLayout()
        self._tone_label = QLabel("Tone: not loaded")
        self._tone_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        btn_tone = QPushButton("Browse…")
        btn_tone.setFixedWidth(80)
        btn_tone.clicked.connect(self._pick_tone)
        tone_row.addWidget(QLabel("🗣"))
        tone_row.addWidget(self._tone_label, stretch=1)
        tone_row.addWidget(btn_tone)
        layout.addLayout(tone_row)

        # Device row
        device_row = QHBoxLayout()
        lbl_device = QLabel("Mic:")
        lbl_device.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        self._device_combo = QComboBox()
        self._device_combo.setToolTip("Select the microphone that will pick up the interview audio")
        device_row.addWidget(QLabel("🎤"))
        device_row.addWidget(lbl_device)
        device_row.addWidget(self._device_combo, stretch=1)
        layout.addLayout(device_row)

    def _populate_devices(self):
        """Populate the device dropdown with available input devices."""
        self._device_combo.clear()
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev["max_input_channels"] > 0:
                    self._device_combo.addItem(f"[{i}] {dev['name']}", userData=i)
            # Try to select device 0 (Sound Mapper) by default
            idx = self._device_combo.findData(0)
            if idx >= 0:
                self._device_combo.setCurrentIndex(idx)
        except Exception as e:
            self._device_combo.addItem(f"Error loading devices: {e}", userData=0)

    def _pick_cv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CV PDF", "", "PDF files (*.pdf)"
        )
        if path:
            self.set_cv_path(path)

    def _pick_tone(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select tone.md", "", "Markdown files (*.md);;Text files (*.txt);;All files (*)"
        )
        if path:
            self.set_tone_path(path)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_cv_path(self, path: str):
        self._cv_path = path
        name = os.path.basename(path)
        self._cv_label.setText(f"{name} ✓")
        self._cv_label.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")

    def set_tone_path(self, path: str):
        self._tone_path = path
        name = os.path.basename(path)
        self._tone_label.setText(f"{name} ✓")
        self._tone_label.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")

    def cv_path(self) -> str:
        return self._cv_path

    def tone_path(self) -> str:
        return self._tone_path

    def device_index(self) -> int:
        return self._device_combo.currentData() or 0
