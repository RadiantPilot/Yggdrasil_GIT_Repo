"""
pid_card.py · PID-kort for én akse med Kp/Ki/Kd-sliders.

Viser aksens navn, tre sliders for Kp/Ki/Kd med spinboxer,
og emitterer gains_changed når brukeren justerer verdiene.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ...config.platform_config import PIDGains


class PidCard(QWidget):
    """PID-kort for én frihetsgrad.

    Emitterer gains_changed(PIDGains) når brukeren endrer
    en av de tre parameterne.
    """

    gains_changed = Signal(object)  # PIDGains

    def __init__(
        self,
        axis_name: str,
        unit: str = "",
        kp_max: float = 10.0,
        ki_max: float = 5.0,
        kd_max: float = 1.0,
    ) -> None:
        super().__init__()
        self._axis_name = axis_name
        self._updating = False

        frame = QFrame(self)
        frame.setFrameStyle(QFrame.StyledPanel)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(frame)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header
        header = QLabel(f"{axis_name}  ({unit})" if unit else axis_name)
        header.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(header)

        self._error_label = QLabel("err —")
        self._error_label.setStyleSheet("font-family: monospace; font-size: 9px; color: #888;")
        layout.addWidget(self._error_label)

        # Sliders
        grid = QGridLayout()
        grid.setSpacing(4)
        self._sliders: list[QSlider] = []
        self._spins: list[QDoubleSpinBox] = []

        for i, (name, mx) in enumerate([("Kp", kp_max), ("Ki", ki_max), ("Kd", kd_max)]):
            lbl = QLabel(name)
            lbl.setStyleSheet("font-size: 11px; font-weight: 500;")
            grid.addWidget(lbl, i, 0)

            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 1000)
            slider.setValue(0)
            slider.setProperty("pid_idx", i)
            slider.setProperty("pid_max", mx)
            slider.valueChanged.connect(self._on_slider)
            grid.addWidget(slider, i, 1)
            self._sliders.append(slider)

            spin = QDoubleSpinBox()
            spin.setRange(0.0, mx)
            spin.setDecimals(3)
            spin.setSingleStep(mx / 100.0)
            spin.setFixedWidth(70)
            spin.setProperty("pid_idx", i)
            spin.setProperty("pid_max", mx)
            spin.valueChanged.connect(self._on_spin)
            grid.addWidget(spin, i, 2)
            self._spins.append(spin)

        layout.addLayout(grid)

    def _on_slider(self, value: int) -> None:
        if self._updating:
            return
        idx = self.sender().property("pid_idx")
        mx = self.sender().property("pid_max")
        self._updating = True
        self._spins[idx].setValue(value / 1000.0 * mx)
        self._updating = False
        self._emit()

    def _on_spin(self, value: float) -> None:
        if self._updating:
            return
        idx = self.sender().property("pid_idx")
        mx = self.sender().property("pid_max")
        self._updating = True
        self._sliders[idx].setValue(int(value / mx * 1000))
        self._updating = False
        self._emit()

    def _emit(self) -> None:
        gains = PIDGains(
            kp=self._spins[0].value(),
            ki=self._spins[1].value(),
            kd=self._spins[2].value(),
        )
        self.gains_changed.emit(gains)

    def set_gains(self, gains: PIDGains) -> None:
        """Sett slider-verdier fra PIDGains (uten å emittere signal)."""
        self._updating = True
        for i, val in enumerate([gains.kp, gains.ki, gains.kd]):
            mx = self._sliders[i].property("pid_max")
            self._spins[i].setValue(val)
            self._sliders[i].setValue(int(val / mx * 1000) if mx > 0 else 0)
        self._updating = False

    def set_error(self, err: float) -> None:
        """Oppdater feilvisningen."""
        self._error_label.setText(f"err {err:.4f}")

    def get_gains(self) -> PIDGains:
        """Hent nåværende PIDGains."""
        return PIDGains(
            kp=self._spins[0].value(),
            ki=self._spins[1].value(),
            kd=self._spins[2].value(),
        )
