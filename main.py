"""
main.py — Entry point for the AI Interview Assistant GUI.

Run with:
    python main.py
"""

import sys
import os
import ctypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from ui.main_window import MainWindow


def hide_from_screen_capture(window):
    """
    Exclude this window from screen capture, screen share, and recordings.
    Works on Windows 10 (2004+) and Windows 11.
    The window appears normally on your screen but shows as black in any capture.
    """
    try:
        hwnd = int(window.winId())
        WDA_EXCLUDEFROMCAPTURE = 0x00000011
        result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        if result:
            print("✅ Window hidden from screen capture")
        else:
            print("⚠️  Could not hide from screen capture (Windows version may not support it)")
    except Exception as e:
        print(f"⚠️  Screen capture hide failed: {e}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI Interview Assistant")

    window = MainWindow()
    window.show()

    # Hide from screen capture after window is fully shown
    # Small delay ensures the native window handle is ready
    QTimer.singleShot(500, lambda: hide_from_screen_capture(window))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()