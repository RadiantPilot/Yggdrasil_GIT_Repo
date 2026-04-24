"""
indicator_lamp.py · Fargelampe med tekst (LED-indikator).

Viser en liten sirkel (grønn/gul/rød/grå) med en etikett ved siden av.
Brukes for statusvisning i overview, safety og toolbar.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

COLORS = {
    "green": QColor(74, 154, 60),
    "yellow": QColor(212, 160, 23),
    "red": QColor(197, 52, 52),
    "gray": QColor(160, 160, 160),
}


class _LedDot(QWidget):
    """Liten sirkulær LED."""

    def __init__(self, color: str = "green", on: bool = True) -> None:
        super().__init__()
        self._color = color
        self._on = on
        self.setFixedSize(12, 12)

    def set_state(self, on: bool, color: str | None = None) -> None:
        if color is not None:
            self._color = color
        self._on = on
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = COLORS.get(self._color, COLORS["gray"])
        if not self._on:
            c = COLORS["gray"]
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(1, 1, 10, 10)
        p.end()


class IndicatorLamp(QWidget):
    """Fargelampe med etikett."""

    def __init__(self, label: str, on: bool = True, color: str = "green") -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._dot = _LedDot(color, on)
        self._label = QLabel(label)
        self._label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._dot)
        layout.addWidget(self._label)

    def set_state(self, on: bool, color: str | None = None) -> None:
        self._dot.set_state(on, color)

    def set_label(self, text: str) -> None:
        self._label.setText(text)
