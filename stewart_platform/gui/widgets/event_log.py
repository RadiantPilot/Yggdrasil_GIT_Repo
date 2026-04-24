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

    def add_event(self, level: str, message: str) -> None:
        """Legg til en ny hendelse."""
        ev = Event(timestamp=time.time(), level=level, message=message)
        self._events.appendleft(ev)
        self._rebuild()

    def _rebuild(self) -> None:
        """Bygg opp visningen fra hendelseslisten."""
        # Fjern alle rader unntatt stretch
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for ev in self._events:
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

            # Sett inn før stretch
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
