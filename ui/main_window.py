"""
ui/main_window.py — Redesigned main window.
Answer is the hero. Everything else is in the top bar as icons.
"""

import os
import sys
import threading

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QDialog,
    QComboBox, QSlider, QLineEdit, QSizePolicy,
    QFrame, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BG       = "#0e0e0f"
BG_CARD  = "#1a1a1d"
BG_CARD2 = "#141416"
ACCENT   = "#4f8ef7"
TEXT     = "#e8e8ea"
TEXT_DIM = "#6b6b75"
TEXT_MID = "#4a4a52"
SUCCESS  = "#3dd68c"
DANGER   = "#e05c5c"
BORDER   = "#2a2a2e"
BORDER2  = "#1e1e22"
Q_COLOR  = "#6b7faa"

STYLESHEET = f"""
QMainWindow, QWidget, QDialog {{
    background-color: {BG};
    color: {TEXT};
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}}
QPushButton {{
    background: none;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    color: {TEXT_DIM};
    font-size: 11px;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: {TEXT}; background: {BG_CARD}; }}
QPushButton#btn_stop {{
    background: {DANGER};
    border: none;
    color: white;
    font-weight: 600;
    font-size: 11px;
    padding: 5px 14px;
}}
QPushButton#btn_stop:hover {{ background: #c94444; }}
QPushButton#btn_start {{
    background: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
    font-size: 11px;
    padding: 5px 14px;
}}
QPushButton#btn_start:hover {{ background: #3d7de8; }}
QPushButton#btn_start:disabled {{ background: #2a4a8a; color: #5a6a8a; }}
QPushButton#btn_export {{
    color: {SUCCESS};
    border-color: {SUCCESS};
}}
QPushButton#btn_export:hover {{ background: {SUCCESS}; color: {BG}; }}
QPushButton#btn_export:disabled {{ color: {TEXT_MID}; border-color: {BORDER}; }}
QComboBox {{
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
}}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: #2a4a8a;
}}
QLineEdit {{
    background: {BG_CARD2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QSlider::groove:horizontal {{
    height: 4px; background: {BORDER}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT}; width: 14px; height: 14px;
    margin: -5px 0; border-radius: 7px;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QTextEdit {{
    background: {BG_CARD2};
    color: {TEXT};
    border: none;
    padding: 4px;
    font-size: 11px;
    font-family: 'Consolas', monospace;
}}
QScrollBar:vertical {{ background: {BG}; width: 6px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; }}
"""


# ── Settings dialogs ──────────────────────────────────────────────────────────

class MicDialog(QDialog):
    def __init__(self, current_index, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Microphone")
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Select microphone:"))
        self.combo = QComboBox()
        try:
            import sounddevice as sd
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_input_channels"] > 0:
                    self.combo.addItem(f"[{i}] {dev['name']}", userData=i)
            idx = self.combo.findData(current_index)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
        except Exception as e:
            self.combo.addItem(f"Error: {e}", userData=0)
        layout.addWidget(self.combo)
        btn = QPushButton("Confirm")
        btn.setObjectName("btn_start")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def selected_index(self):
        return self.combo.currentData() or 0


class FilesDialog(QDialog):
    def __init__(self, cv_path, tone_path, job_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Files")
        self.setFixedWidth(420)
        self._cv   = cv_path
        self._tone = tone_path
        self._job_text = job_text
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("CV (PDF):"))
        cv_row = QHBoxLayout()
        self._cv_label = QLabel(os.path.basename(cv_path) if cv_path else "Not selected")
        self._cv_label.setStyleSheet(f"color: {SUCCESS if cv_path else TEXT_DIM};")
        btn_cv = QPushButton("Browse…")
        btn_cv.clicked.connect(self._pick_cv)
        cv_row.addWidget(self._cv_label, stretch=1)
        cv_row.addWidget(btn_cv)
        layout.addLayout(cv_row)

        layout.addWidget(QLabel("Tone guide (tone.md):"))
        tone_row = QHBoxLayout()
        self._tone_label = QLabel(os.path.basename(tone_path) if tone_path else "Not selected")
        self._tone_label.setStyleSheet(f"color: {SUCCESS if tone_path else TEXT_DIM};")
        btn_tone = QPushButton("Browse…")
        btn_tone.clicked.connect(self._pick_tone)
        tone_row.addWidget(self._tone_label, stretch=1)
        tone_row.addWidget(btn_tone)
        layout.addLayout(tone_row)

        layout.addWidget(QLabel("Job description (paste text):"))
        self._job_desc = QTextEdit()
        self._job_desc.setPlaceholderText("Paste the job posting here — role, responsibilities, requirements…")
        self._job_desc.setMaximumHeight(120)
        self._job_desc.setStyleSheet(f"""
            QTextEdit {{
                background: #141416;
                color: #e8e8ea;
                border: 1px solid #2a2a2e;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }}
        """)
        if hasattr(self, '_job_text') and self._job_text:
            self._job_desc.setPlainText(self._job_text)
        layout.addWidget(self._job_desc)

        btn = QPushButton("Done")
        btn.setObjectName("btn_start")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def _pick_cv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CV", "", "PDF (*.pdf)")
        if path:
            self._cv = path
            self._cv_label.setText(os.path.basename(path))
            self._cv_label.setStyleSheet(f"color: {SUCCESS};")

    def _pick_tone(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select tone file", "", "Markdown (*.md);;Text (*.txt);;All (*)")
        if path:
            self._tone = path
            self._tone_label.setText(os.path.basename(path))
            self._tone_label.setStyleSheet(f"color: {SUCCESS};")

    def cv_path(self):   return self._cv
    def tone_path(self): return self._tone
    def job_text(self):  return self._job_desc.toPlainText().strip()


class SettingsDialog(QDialog):
    def __init__(self, opacity, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedWidth(300)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Window opacity:"))
        row = QHBoxLayout()
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(40, 100)
        self._slider.setValue(int(opacity * 100))
        self._val = QLabel(f"{int(opacity*100)}%")
        self._slider.valueChanged.connect(lambda v: (
            self._val.setText(f"{v}%"),
            parent.setWindowOpacity(v / 100) if parent else None
        ))
        row.addWidget(self._slider)
        row.addWidget(self._val)
        layout.addLayout(row)

        btn = QPushButton("Done")
        btn.setObjectName("btn_start")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def opacity(self): return self._slider.value() / 100


# ── Session Worker ────────────────────────────────────────────────────────────

class SessionWorker(QObject):
    status_update  = pyqtSignal(str)
    partial_update = pyqtSignal(str)
    log_update     = pyqtSignal(str)
    question_found = pyqtSignal(str)
    token_received = pyqtSignal(str)
    answer_done    = pyqtSignal(str, str)
    error          = pyqtSignal(str)
    model_ready    = pyqtSignal()

    def __init__(self, cv_path, tone_path, device_index, job_text="", parent=None):
        super().__init__(parent)
        self.cv_path      = cv_path
        self.tone_path    = tone_path
        self.device_index = device_index
        self.job_text     = job_text
        self._transcriber = None
        self._capture     = None

    def load(self):
        try:
            from cv_parser   import load_cv
            from tone_loader import load_tone
            from transcriber import Transcriber

            self.status_update.emit("Loading CV…")
            cv_text = load_cv(self.cv_path)
            self.status_update.emit("Loading tone guide…")
            tone = load_tone(self.tone_path)
            self.status_update.emit("Loading Whisper model…")

            self._transcriber = Transcriber(
                on_answer    = self._on_answer,
                cv_text      = cv_text,
                tone_content = tone,
                job_text     = self.job_text,
                on_partial = lambda t: self.partial_update.emit(t),
                on_status  = lambda s: self.status_update.emit(s),
            )
            self._transcriber.load()
            self._transcriber.wait_until_ready(timeout=60)
            # Calibrate mic before starting
            self._transcriber.calibrate(duration=2.0)
            self.model_ready.emit()
            self.status_update.emit("Ready")

        except Exception as e:
            self.error.emit(str(e))

    def start_listening(self):
        from audio_capture import AudioCapture
        self._transcriber.start()
        self._capture = AudioCapture(
            device_index   = self.device_index,
            on_audio_chunk = self._transcriber.feed,
            source         = "microphone",
            chunk_seconds  = 1,
        )
        self._capture.start()
        self.status_update.emit("Listening…")

    def stop_listening(self):
        if self._capture:     self._capture.stop()
        if self._transcriber: self._transcriber.stop()
        self.status_update.emit("Stopped")

    def _on_answer(self, question, answer):
        self.log_update.emit(f"❓ Question: {question[:80]}")
        self.log_update.emit(f"✅ Answer ready ({len(answer)} chars)")
        self.question_found.emit(question)
        for token in answer.split(" "):
            self.token_received.emit(token + " ")
        self.answer_done.emit(question, answer)


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Interview Assistant")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window)
        self.resize(480, 800)
        self.setMinimumSize(360, 400)
        self.setStyleSheet(STYLESHEET)
        self.setWindowOpacity(0.95)

        self._worker     = None
        self._thread     = None
        self._qa_pairs   = []
        self._listening  = False
        self._cv_path    = ""
        self._tone_path  = ""
        self._device_idx = 0
        self._job_text   = ""
        self._opacity    = 0.95

        self._load_defaults()
        self._build_ui()

    def _load_defaults(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cv   = os.path.join(base, "cv.pdf")
        tone = os.path.join(base, "tone.md")
        if os.path.exists(cv):   self._cv_path   = cv
        if os.path.exists(tone): self._tone_path = tone

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────────
        top = QWidget()
        top.setStyleSheet(f"background: {BG}; border-bottom: 1px solid {BORDER2};")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(6)

        # Status dot + label
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {TEXT_MID}; font-size: 10px;")
        self._status_lbl = QLabel("Idle")
        self._status_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; letter-spacing: 0.5px;")
        top_layout.addWidget(self._dot)
        top_layout.addWidget(self._status_lbl)
        top_layout.addStretch()

        # Icon buttons
        self._btn_mic = QPushButton()
        self._btn_mic.setFixedSize(30, 28)
        self._btn_mic.setToolTip("Change microphone")
        self._btn_mic.setText("🎤")
        self._btn_mic.clicked.connect(self._open_mic_dialog)

        self._btn_files = QPushButton()
        self._btn_files.setFixedSize(30, 28)
        self._btn_files.setToolTip("CV & tone files")
        self._btn_files.setText("📄")
        self._btn_files.clicked.connect(self._open_files_dialog)

        self._btn_settings = QPushButton()
        self._btn_settings.setFixedSize(30, 28)
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.setText("⚙")
        self._btn_settings.clicked.connect(self._open_settings_dialog)

        self._btn_export = QPushButton("Export")
        self._btn_export.setObjectName("btn_export")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._on_export)

        self._btn_start = QPushButton("▶")
        self._btn_start.setObjectName("btn_start")
        self._btn_start.setFixedSize(32, 28)
        self._btn_start.setToolTip("Start listening")
        self._btn_start.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS};
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: #2ab87a; }}
        """)
        self._btn_start.clicked.connect(self._on_start)

        self._btn_stop = QPushButton("■")
        self._btn_stop.setObjectName("btn_stop")
        self._btn_stop.setFixedSize(32, 28)
        self._btn_stop.setToolTip("Stop listening")
        self._btn_stop.setVisible(False)
        self._btn_stop.setStyleSheet(f"""
            QPushButton {{
                background: {DANGER};
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: #c94444; }}
        """)
        self._btn_stop.clicked.connect(self._on_stop)

        for w in [self._btn_mic, self._btn_files, self._btn_settings,
                  self._btn_export, self._btn_start, self._btn_stop]:
            top_layout.addWidget(w)

        layout.addWidget(top)

        # ── Live transcript bar ───────────────────────────────────────────────
        self._live_bar = QLabel("")
        self._live_bar.setWordWrap(True)
        self._live_bar.setStyleSheet(f"""
            color: {TEXT_MID};
            font-size: 11px;
            font-style: italic;
            padding: 6px 14px;
            background: {BG};
            border-bottom: 1px solid {BORDER2};
            min-height: 24px;
        """)
        layout.addWidget(self._live_bar)



        # ── Answer panel (segments + nav + override) ─────────────────────────
        from ui.answer_panel import AnswerPanel
        self._answer_panel = AnswerPanel()
        self._answer_panel.manual_question.connect(self._on_manual_question)
        layout.addWidget(self._answer_panel, stretch=1)

        # ── History (collapsed) ───────────────────────────────────────────────
        hist_widget = QWidget()
        hist_widget.setStyleSheet(f"background: {BG}; border-top: 1px solid {BORDER2};")
        hist_layout = QVBoxLayout(hist_widget)
        hist_layout.setContentsMargins(14, 6, 14, 6)
        hist_layout.setSpacing(4)

        hist_top = QHBoxLayout()
        hist_lbl = QLabel("PREVIOUS Q&As")
        hist_lbl.setStyleSheet(f"color: {TEXT_MID}; font-size: 10px; letter-spacing: 0.8px;")
        self._hist_toggle = QPushButton("▼ Show")
        self._hist_toggle.setStyleSheet(f"color: {TEXT_MID}; background: none; border: none; font-size: 10px; padding: 0;")
        self._hist_toggle.clicked.connect(self._toggle_history)
        hist_top.addWidget(hist_lbl)
        hist_top.addStretch()
        hist_top.addWidget(self._hist_toggle)
        hist_layout.addLayout(hist_top)

        self._hist_box = QTextEdit()
        self._hist_box.setReadOnly(True)
        self._hist_box.setVisible(False)
        self._hist_box.setMaximumHeight(120)

        self._hist_box.setFont(QFont("Segoe UI", 11))
        hist_layout.addWidget(self._hist_box)

        layout.addWidget(hist_widget)

        # ── Debug log (hidden by default) ─────────────────────────────────────
        log_widget = QWidget()
        log_widget.setStyleSheet(f"background: {BG}; border-top: 1px solid {BORDER2};")
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(14, 4, 14, 6)
        log_layout.setSpacing(2)

        log_top = QHBoxLayout()
        log_lbl = QLabel("DEBUG LOG")
        log_lbl.setStyleSheet(f"color: {TEXT_MID}; font-size: 10px; letter-spacing: 0.8px;")
        self._log_toggle = QPushButton("▼ Show")
        self._log_toggle.setStyleSheet(f"color: {TEXT_MID}; background: none; border: none; font-size: 10px; padding: 0;")
        self._log_toggle.clicked.connect(self._toggle_log)
        log_top.addWidget(log_lbl)
        log_top.addStretch()
        log_top.addWidget(self._log_toggle)
        log_layout.addLayout(log_top)

        self._log_box = QTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setVisible(False)
        self._log_box.setMaximumHeight(120)
        self._log_box.setStyleSheet(f"QTextEdit {{ background: #0a0a0b; color: #6bff8a; border: none; font-size: 10px; }}")
        log_layout.addWidget(self._log_box)

        layout.addWidget(log_widget)

    # ── Dialog handlers ───────────────────────────────────────────────────────

    def _open_mic_dialog(self):
        dlg = MicDialog(self._device_idx, self)
        if dlg.exec():
            self._device_idx = dlg.selected_index()
        self._answer_panel._override_input.setFocus()

    def _open_files_dialog(self):
        dlg = FilesDialog(self._cv_path, self._tone_path, self._job_text, self)
        if dlg.exec():
            self._cv_path   = dlg.cv_path()
            self._tone_path = dlg.tone_path()
            self._job_text  = dlg.job_text()
        self._answer_panel._override_input.setFocus()

    def _open_settings_dialog(self):
        dlg = SettingsDialog(self._opacity, self)
        if dlg.exec():
            self._opacity = dlg.opacity()
            self.setWindowOpacity(self._opacity)
        self._answer_panel._override_input.setFocus()

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_start(self):
        if not self._cv_path or not os.path.exists(self._cv_path):
            self._set_status("Select a CV first", DANGER)
            return
        if not self._tone_path or not os.path.exists(self._tone_path):
            self._set_status("Select a tone file first", DANGER)
            return

        self._answer_panel.clear()
        self._answer_panel._q_label.setText("Waiting for a question…")
        self._btn_start.setVisible(False)
        self._btn_stop.setVisible(True)
        self._set_status("Loading…", TEXT_DIM)

        self._thread = QThread()
        self._worker = SessionWorker(self._cv_path, self._tone_path, self._device_idx, self._job_text)
        self._worker.moveToThread(self._thread)

        self._worker.status_update.connect(self._on_status_update)
        self._worker.partial_update.connect(self._on_partial)
        self._worker.partial_update.connect(self._answer_panel.set_partial)
        self._worker.log_update.connect(self._append_log)
        self._worker.question_found.connect(self._answer_panel.set_question)
        self._worker.question_found.connect(self._on_question_found)
        self._worker.token_received.connect(self._answer_panel.append_token)
        self._worker.answer_done.connect(self._on_answer_done)
        self._worker.error.connect(self._on_error)
        self._worker.model_ready.connect(lambda: self._worker.start_listening())
        self._worker.status_update.connect(lambda s: self._append_log(f"ℹ️ {s}"))

        self._thread.started.connect(self._worker.load)
        self._thread.start()
        self._listening = True

    def _on_stop(self):
        if self._worker: self._worker.stop_listening()
        if self._thread:
            self._thread.quit()
            self._thread.wait(3000)
        self._listening = False
        self._btn_start.setVisible(True)
        self._btn_stop.setVisible(False)
        if self._qa_pairs: self._btn_export.setEnabled(True)
        self._set_status("Stopped", TEXT_DIM)

    def _on_export(self):
        if not self._qa_pairs: return
        path, _ = QFileDialog.getSaveFileName(self, "Export", "session.txt",
                                               "Text (*.txt);;PDF (*.pdf)")
        if path:
            from session_exporter import export_session
            try:
                export_session(self._qa_pairs, path)
                self._set_status(f"Exported: {os.path.basename(path)}", SUCCESS)
            except Exception as e:
                self._set_status(f"Export failed: {e}", DANGER)


    def _copy_question(self):
        pass  # copy handled by answer_panel

    # ── Signal handlers ───────────────────────────────────────────────────────

    def _on_status_update(self, msg: str):
        color = TEXT_DIM
        if "listen" in msg.lower():   color = SUCCESS
        if "generat" in msg.lower() or "check" in msg.lower(): color = ACCENT
        if "error" in msg.lower() or "fail" in msg.lower():    color = DANGER

        self._set_status(msg, color)

    def _on_partial(self, text: str):
        if text:
            display = text if len(text) <= 120 else "…" + text[-120:]
            self._live_bar.setText(f"🎤 {display}")
        else:
            self._live_bar.setText("")
        self._append_log(f"🎤 {text}" if text else "")

    def _on_manual_question(self, text=None):
        """Delegate manual question to answer panel."""
        if text is None:
            return
        if self._worker and self._worker._transcriber:
            with self._worker._transcriber._transcript_lock:
                self._worker._transcriber._transcript = text

    def _on_question_found(self, question: str):
        pass  # handled by answer_panel



    def _on_answer_done(self, question: str, answer: str):
        self._qa_pairs.append((question, answer))
        self._btn_export.setEnabled(True)
        self._pulse_answer_box()
        q_num = len(self._qa_pairs)
        self._hist_box.append(f"Q{q_num}: {question}\nA{q_num}: {answer[:120]}…\n")
        # History stays collapsed unless user opens it manually

    def _on_error(self, msg: str):
        self._set_status(f"Error: {msg}", DANGER)
        self._append_log(f"❌ {msg}")

    def _append_log(self, msg: str):
        if not msg: return
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._log_box.append(f"[{ts}] {msg}")
        sb = self._log_box.verticalScrollBar()
        sb.setValue(sb.maximum())
        # Log stays collapsed unless user opens it manually

    def _set_status(self, text: str, color: str = TEXT_DIM):
        self._status_lbl.setText(text.upper())
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 11px; letter-spacing: 0.5px;")
        dot_color = SUCCESS if "listen" in text.lower() else (ACCENT if "check" in text.lower() or "generat" in text.lower() else TEXT_MID)
        self._dot.setStyleSheet(f"color: {dot_color}; font-size: 10px;")

    def _toggle_history(self):
        v = self._hist_box.isVisible()
        self._hist_box.setVisible(not v)
        self._hist_toggle.setText("▲ Hide" if not v else "▼ Show")

    def _toggle_log(self):
        v = self._log_box.isVisible()
        self._log_box.setVisible(not v)
        self._log_toggle.setText("▲ Hide" if not v else "▼ Show")

    def _pulse_answer_box(self):
        """Flash the answer panel border briefly to signal a new answer arrived."""
        from PyQt6.QtCore import QTimer

        pulse_on = f"""
            QTextEdit {{
                background: {BG};
                color: {TEXT};
                border: 2px solid {ACCENT};
                border-radius: 4px;
                padding: 14px 12px;
                line-height: 1.7;
                font-family: 'Segoe UI';
                font-size: 50px;
                font-weight: bold;
            }}
        """
        pulse_off = f"""
            QTextEdit {{
                background: {BG};
                color: {TEXT};
                border: none;
                padding: 16px 14px;
                line-height: 1.7;
                font-family: 'Segoe UI';
                font-size: 50px;
                font-weight: bold;
            }}
        """

        flashes = [True, False, True, False, True, False]
        self._pulse_step = 0

        def step():
            if self._pulse_step >= len(flashes):
                self._answer_panel._answer_box.setStyleSheet(pulse_off)
                return
            self._answer_panel._answer_box.setStyleSheet(pulse_on if flashes[self._pulse_step] else pulse_off)
            self._pulse_step += 1
            QTimer.singleShot(500, step)

        step()

    def closeEvent(self, event):
        if self._worker: self._worker.stop_listening()
        if self._thread:
            self._thread.quit()
            self._thread.wait(2000)
        event.accept()