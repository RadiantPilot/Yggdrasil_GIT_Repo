"""
servo_bars.py · Horisontale bar-grafer for 6 servovinkler.

Viser servo-ID, vinkelverdi og en horisontal bar som indikerer
nåværende posisjon innenfor grensene.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class ServoBars(QWidget):
    """Kompakt servo-vinkelvisning for 6 servoer."""

    def __init__(self, min_angle: float = -60.0, max_angle: float = 60.0) -> None:
        super().__init__()
        self._min = min_angle
        self._max = max_angle
        self._bars: list[QProgressBar] = []
        self._labels: list[QLabel] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for i in range(6):
            row = QHBoxLayout()
            row.setSpacing(8)

            name = QLabel(f"S{i + 1}")
            name.setFixedWidth(24)
            name.setStyleSheet("font-size: 11px;")
            row.addWidget(name)

            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            row.addWidget(bar, 1)

            val = QLabel("0.0°")
            val.setFixedWidth(55)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet("font-family: monospace; font-size: 10px;")
            row.addWidget(val)

            layout.addLayout(row)
            self._bars.append(bar)
            self._labels.append(val)

    def update_angles(self, angles: list[float]) -> None:
        """Oppdater alle 6 servo-vinkler."""
        for i, angle in enumerate(angles[:6]):
            pct = (angle - self._min) / (self._max - self._min)
            self._bars[i].setValue(int(max(0, min(1, pct)) * 1000))
            self._labels[i].setText(f"{angle:+.1f}°")
