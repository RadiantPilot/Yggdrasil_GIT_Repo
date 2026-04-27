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
        # Indeks 0..2 for Kp/Ki/Kd — peker på hvilken parameter
        # knappenavigasjonen skal justere når kortet er i edit-mode.
        self._active_param_index = 0

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

    # ------------------------------------------------------------------
    # Navigable-implementasjon — styres av FocusManager.
    # nav_vertical bytter mellom Kp/Ki/Kd, nav_horizontal justerer aktiv
    # verdi med spinbox-stegstørrelse.
    # ------------------------------------------------------------------

    def set_focused(self, focused: bool) -> None:
        """Markeres som fokusert i nav-mode (uten edit)."""
        # apply_nav_state håndterer faktisk stylesheet; vi tar imot
        # signalet for symmetri og ev. semantikk-spesifikk respons.
        if focused:
            self._highlight_active_param()
        else:
            self._clear_active_param_highlight()

    def set_edit_mode(self, edit: bool) -> None:
        """Tegn ekstra fremheving av aktiv parameter når i edit."""
        if edit:
            self._highlight_active_param()
        else:
            self._clear_active_param_highlight()

    def nav_vertical(self, delta: int) -> None:
        """Bytt aktiv koeffisient (Kp ↔ Ki ↔ Kd)."""
        self._active_param_index = (self._active_param_index + delta) % 3
        self._highlight_active_param()

    def nav_horizontal(self, delta: int) -> None:
        """Juster aktiv koeffisient med spinbox-steg."""
        spin = self._spins[self._active_param_index]
        spin.setValue(spin.value() + delta * spin.singleStep())

    def _highlight_active_param(self) -> None:
        """Sett en bakgrunnsfarge på spin-boksen som er aktiv."""
        for i, spin in enumerate(self._spins):
            if i == self._active_param_index:
                spin.setStyleSheet("background: #f9d77e;")
            else:
                spin.setStyleSheet("")

    def _clear_active_param_highlight(self) -> None:
        for spin in self._spins:
            spin.setStyleSheet("")
