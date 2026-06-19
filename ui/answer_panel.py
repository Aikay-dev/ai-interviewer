"""
ui/answer_panel.py — Segmented answer display.
Each Q&A is its own segment. Navigate with up/down arrows.
New answers append to the bottom without affecting the current view.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor

BG       = "#0e0e0f"
BG_CARD  = "#1a1a1d"
BG_CARD2 = "#141416"
ACCENT   = "#4f8ef7"
TEXT     = "#e8e8ea"
TEXT_DIM = "#6b6b75"
TEXT_MID = "#4a4a52"
SUCCESS  = "#3dd68c"
BORDER   = "#2a2a2e"
BORDER2  = "#1e1e22"
Q_COLOR  = "#6b7faa"


class AnswerPanel(QWidget):

    manual_question = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._segments = []      # list of {"question": str, "answer": str}
        self._current  = -1      # index of currently viewed segment
        self._building = False   # True while streaming into latest segment
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Question label ────────────────────────────────────────────────────
        q_row = QWidget()
        q_row.setStyleSheet(f"background: {BG}; border-bottom: 1px solid {BORDER2};")
        q_layout = QHBoxLayout(q_row)
        q_layout.setContentsMargins(14, 6, 14, 6)
        q_layout.setSpacing(8)

        self._q_label = QLabel("Waiting for a question…")
        self._q_label.setWordWrap(True)
        self._q_label.setStyleSheet(f"color: {Q_COLOR}; font-size: 12px; font-style: italic;")

        self._btn_copy_q = QPushButton("Copy")
        self._btn_copy_q.setFixedWidth(48)
        self._btn_copy_q.setStyleSheet(f"font-size: 10px; padding: 3px 6px; color: {TEXT_DIM}; border: 1px solid {BORDER}; border-radius: 4px; background: none;")
        self._btn_copy_q.clicked.connect(self._copy_question)

        q_layout.addWidget(self._q_label, stretch=1)
        q_layout.addWidget(self._btn_copy_q)
        layout.addWidget(q_row)

        # ── Main area: answer box + nav buttons ───────────────────────────────
        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(0)

        # Answer box
        self._answer_box = QTextEdit()
        self._answer_box.setReadOnly(True)
        self._answer_box.setPlaceholderText("Answer will appear here…")
        self._answer_box.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self._answer_box.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._answer_box.setStyleSheet(f"""
            QTextEdit {{
                background: {BG};
                color: {TEXT};
                border: none;
                padding: 16px 14px;
                font-family: 'Segoe UI';
                font-size: 22px;
                font-weight: bold;
            }}
        """)
        self._answer_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._answer_box.setSizeAdjustPolicy(QTextEdit.SizeAdjustPolicy.AdjustIgnored)
        main_row.addWidget(self._answer_box, stretch=1)

        # Nav buttons column
        nav_col = QWidget()
        nav_col.setFixedWidth(44)
        nav_col.setStyleSheet(f"background: {BG}; border-left: 1px solid {BORDER2};")
        nav_layout = QVBoxLayout(nav_col)
        nav_layout.setContentsMargins(4, 8, 4, 8)
        nav_layout.setSpacing(6)

        self._btn_up = QPushButton("▲")
        self._btn_up.setFixedSize(36, 48)
        self._btn_up.setToolTip("Previous answer")
        self._btn_up.setStyleSheet(self._nav_btn_style(False))
        self._btn_up.clicked.connect(self._go_prev)

        self._seg_label = QLabel("0/0")
        self._seg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._seg_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._seg_label.setStyleSheet(f"color: {TEXT}; padding: 4px 0;")
        self._seg_label.setWordWrap(True)

        self._btn_down = QPushButton("▼")
        self._btn_down.setFixedSize(36, 48)
        self._btn_down.setToolTip("Next answer")
        self._btn_down.setStyleSheet(self._nav_btn_style(False))
        self._btn_down.clicked.connect(self._go_next)

        nav_layout.addWidget(self._btn_up)
        nav_layout.addWidget(self._seg_label)
        nav_layout.addWidget(self._btn_down)
        nav_layout.addStretch()

        main_row.addWidget(nav_col)
        layout.addLayout(main_row, stretch=1)

        # ── Override input ────────────────────────────────────────────────────
        override = QWidget()
        override.setStyleSheet(f"background: {BG}; border-top: 1px solid {BORDER2};")
        ov_layout = QHBoxLayout(override)
        ov_layout.setContentsMargins(14, 8, 14, 8)
        ov_layout.setSpacing(8)

        self._override_input = QLineEdit()
        self._override_input.setPlaceholderText("Type or correct a question and press Enter…")
        self._override_input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_CARD};
                color: {TEXT};
                border: 1px solid {ACCENT};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self._override_input.returnPressed.connect(self._on_override)
        # Always return focus to input after any button click
        for btn in [self._btn_up, self._btn_down, self._btn_copy_q]:
            btn.clicked.connect(lambda: self._override_input.setFocus())

        btn_ask = QPushButton("Ask")
        btn_ask.setFixedWidth(52)
        btn_ask.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white; border: none;
                border-radius: 6px; padding: 8px 12px;
                font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #3d7de8; }}
        """)
        btn_ask.clicked.connect(self._on_override)

        ov_layout.addWidget(self._override_input)
        ov_layout.addWidget(btn_ask)
        layout.addWidget(override)
        # Set focus to input on startup
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._override_input.setFocus)

    def _nav_btn_style(self, highlight: bool = False):
        bg = ACCENT if highlight else BG_CARD
        color = "white" if highlight else TEXT_DIM
        border = ACCENT if highlight else BORDER
        return f"""
            QPushButton {{
                background: {bg};
                color: {color};
                border: 2px solid {border};
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ color: white; border-color: {ACCENT}; background: {ACCENT}; }}
            QPushButton:disabled {{ color: {TEXT_MID}; border-color: {BORDER}; background: {BG_CARD}; }}
        """

    # ── Public API ────────────────────────────────────────────────────────────

    def set_question(self, question: str):
        """Called when a new question is detected — create a new segment."""
        self._segments.append({"question": question, "answer": ""})
        self._building = True
        self._q_label.setText(f'"{question}"')
        self._override_input.clear()
        self._update_nav()






    @pyqtSlot(str)
    def set_partial(self, text: str):
        pass  # handled by main window live bar

    @pyqtSlot(str)
    def append_token(self, token: str):
        """Stream token into the latest segment."""
        if not self._segments:
            return
        latest = len(self._segments) - 1
        self._segments[latest]["answer"] += token

        # Only update the display if user is viewing the latest segment
        if self._current == latest:
            scrollbar = self._answer_box.verticalScrollBar()
            pos = scrollbar.value()
            doc_cursor = QTextCursor(self._answer_box.document())
            doc_cursor.movePosition(QTextCursor.MoveOperation.End)
            doc_cursor.insertText(token)
            scrollbar.setValue(pos)

    def mark_done(self):
        self._building = False

    def clear(self):
        self._segments = []
        self._current  = -1
        self._building = False
        self._answer_box.clear()
        self._q_label.setText("Waiting for a question…")
        self._override_input.clear()
        self._update_nav()

    def clear_answer(self):
        self._answer_box.clear()

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go_prev(self):
        if self._current > 0:
            self._current -= 1
            self._show_segment(self._current)
            self._update_nav()
        self._override_input.setFocus()

    def _go_next(self):
        latest = len(self._segments) - 1
        if self._current < latest:
            self._current += 1
            self._show_segment(self._current)
            self._update_nav()
            if self._current == latest:
                self._btn_down.setStyleSheet(self._nav_btn_style(False))
        self._override_input.setFocus()

    def _show_segment(self, index: int):
        if 0 <= index < len(self._segments):
            seg = self._segments[index]
            self._q_label.setText(f'"{seg["question"]}"')
            self._answer_box.setPlainText(seg["answer"])
            self._answer_box.verticalScrollBar().setValue(0)

    def _update_nav(self):
        total = len(self._segments)
        if total == 0:
            self._current = -1
            self._seg_label.setText("0/0")
            self._btn_up.setEnabled(False)
            self._btn_down.setEnabled(False)
            return

        # Auto-advance to latest when first segment arrives
        if self._current == -1:
            self._current = 0

        latest = total - 1

        # If user was on latest, stay on latest
        if self._current == latest - 1 and not self._building:
            pass

        self._seg_label.setText(f"{self._current + 1}/{total}")
        self._btn_up.setEnabled(self._current > 0)
        self._btn_down.setEnabled(self._current < latest)
        # Highlight down if there are newer segments
        has_newer = self._current < latest
        self._btn_down.setStyleSheet(self._nav_btn_style(has_newer))
        self._btn_up.setStyleSheet(self._nav_btn_style(False))

    # ── Override ──────────────────────────────────────────────────────────────

    def _on_override(self):
        text = self._override_input.text().strip()
        if not text:
            return
        self._override_input.clear()
        self.manual_question.emit(text)

    def _copy_question(self):
        text = self._q_label.text().strip('"')
        if text and text != "Waiting for a question…":
            self._override_input.setText(text)
            self._override_input.setFocus()
            self._override_input.setCursorPosition(len(text))

    def append_log(self, msg: str):
        pass  # log handled by main window