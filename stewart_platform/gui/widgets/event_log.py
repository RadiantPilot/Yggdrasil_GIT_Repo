"""
event_log.py · Rullerende hendelsesliste.

Viser tidsstempel, alvorlighetsgrad og melding for de siste N
hendelsene. Brukes i overview- og safety-tabs.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget, QHBoxLayout


@dataclass
class Event:
    """Én hendelse i loggen."""
    timestamp: float
    level: str  # "INFO", "WARN", "FAIL"
    message: str


class EventLog(QWidget):
    """Rullerende hendelsesliste med fargekodet alvorlighetsgrad."""

    def __init__(self, max_events: int = 50) -> None:
        super().__init__()
        self._events: deque[Event] = deque(maxlen=max_events)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._rows_layout = QVBoxLayout(self._container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)
        self._rows_layout.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def __len__(self) -> int:
        return len(self._events)

    def add_event(self, level: str, message: str) -> None:
        """Legg til en ny hendelse øverst; fjern eldste rad hvis loggen er full."""
        ev = Event(timestamp=time.time(), level=level, message=message)
        was_full = len(self._events) == self._events.maxlen
        self._events.appendleft(ev)

        self._rows_layout.insertWidget(0, self._make_row(ev))

        if was_full:
            # Eldste widget er siste rad før stretch
            idx = self._rows_layout.count() - 2
            item = self._rows_layout.takeAt(idx)
            if item.widget():
                item.widget().deleteLater()

    def _make_row(self, ev: Event) -> QWidget:
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 2, 0, 2)
        rl.setSpacing(10)

        ts = time.strftime("%H:%M:%S", time.localtime(ev.timestamp))
        ts_label = QLabel(ts)
        ts_label.setFixedWidth(60)
        ts_label.setStyleSheet("font-family: monospace; font-size: 10px; color: #888;")
        rl.addWidget(ts_label)

        level_colors = {"INFO": "#666", "WARN": "#d4a017", "FAIL": "#c53434"}
        lv_label = QLabel(ev.level)
        lv_label.setFixedWidth(40)
        lv_label.setStyleSheet(
            f"font-size: 10px; font-weight: bold; "
            f"color: {level_colors.get(ev.level, '#666')};"
        )
        rl.addWidget(lv_label)

        msg = QLabel(ev.message)
        msg.setStyleSheet("font-size: 11px;")
        msg.setWordWrap(True)
        rl.addWidget(msg, 1)
        return row
