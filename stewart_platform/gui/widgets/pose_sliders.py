"""
pose_sliders.py · 6-DOF slider-panel med numerisk input.

Gir 6 sliders (X, Y, Z, Roll, Pitch, Yaw) med tilhørende
QDoubleSpinBox for presis input. Emitterer pose_changed-signal
når brukeren endrer en verdi.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QSlider,
    QWidget,
)
from PySide6.QtCore import Qt


_AXES = [
    ("X", "mm", -30.0, 30.0, 0.0),
    ("Y", "mm", -30.0, 30.0, 0.0),
    ("Z", "mm", 15.0, 40.0, 25.0),
    ("Roll", "°", -20.0, 20.0, 0.0),
    ("Pitch", "°", -20.0, 20.0, 0.0),
    ("Yaw", "°", -25.0, 25.0, 0.0),
]


class PoseSliders(QWidget):
    """6-DOF slider-panel med numerisk input.

    Emitterer pose_changed med dict {name: value} når brukeren
    justerer en slider eller spinbox.
    """

    pose_changed = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._sliders: list[QSlider] = []
        self._spinboxes: list[QDoubleSpinBox] = []
        self._current_labels: list[QLabel] = []
        self._axis_labels: list[QLabel] = []
        self._updating = False
        # Aktiv akse 0..5 for knappenavigasjon i edit-mode.
        self._active_axis_index = 0

        grid = QGridLayout(self)
        grid.setSpacing(8)

        # Header
        for col, header in enumerate(["Akse", "Mål", "Input", "Nå"]):
            lbl = QLabel(header)
            lbl.setStyleSheet("font-size: 10px; color: #888;")
            grid.addWidget(lbl, 0, col)

        for i, (name, unit, mn, mx, default) in enumerate(_AXES):
            row = i + 1
            # Akse-navn
            lbl = QLabel(f"{name} ({unit})")
            lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
            grid.addWidget(lbl, row, 0)
            self._axis_labels.append(lbl)

            # Slider
            slider = QSlider(Qt.Horizontal)
            slider.setRange(int(mn * 100), int(mx * 100))
            slider.setValue(int(default * 100))
            slider.setProperty("axis_index", i)
            slider.valueChanged.connect(self._on_slider_changed)
            grid.addWidget(slider, row, 1)
            self._sliders.append(slider)

            # Spinbox
            spin = QDoubleSpinBox()
            spin.setRange(mn, mx)
            spin.setValue(default)
            spin.setDecimals(2)
            spin.setSingleStep(0.5)
            spin.setSuffix(f" {unit}")
            spin.setFixedWidth(90)
            spin.setProperty("axis_index", i)
            spin.valueChanged.connect(self._on_spin_changed)
            grid.addWidget(spin, row, 2)
            self._spinboxes.append(spin)

            # Nåværende verdi
            cur = QLabel("—")
            cur.setStyleSheet("font-family: monospace; font-size: 11px; color: #888;")
            cur.setFixedWidth(60)
            cur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(cur, row, 3)
            self._current_labels.append(cur)

    def _on_slider_changed(self, value: int) -> None:
        if self._updating:
            return
        idx = self.sender().property("axis_index")
        self._updating = True
        self._spinboxes[idx].setValue(value / 100.0)
        self._updating = False
        self._emit_pose()

    def _on_spin_changed(self, value: float) -> None:
        if self._updating:
            return
        idx = self.sender().property("axis_index")
        self._updating = True
        self._sliders[idx].setValue(int(value * 100))
        self._updating = False
        self._emit_pose()

    def _emit_pose(self) -> None:
        values = {}
        for i, (name, *_) in enumerate(_AXES):
            values[name.lower()] = self._spinboxes[i].value()
        self.pose_changed.emit(values)

    def get_values(self) -> dict[str, float]:
        """Hent nåværende slider-verdier."""
        return {name.lower(): self._spinboxes[i].value() for i, (name, *_) in enumerate(_AXES)}

    def update_current(self, x: float, y: float, z: float,
                       roll: float, pitch: float, yaw: float) -> None:
        """Oppdater 'nå'-kolonne med gjeldende pose."""
        vals = [x, y, z, roll, pitch, yaw]
        for i, v in enumerate(vals):
            self._current_labels[i].setText(f"{v:+.2f}")

    def reset_to_home(self) -> None:
        """Sett alle sliders til default-verdier."""
        self._updating = True
        for i, (_, _, _, _, default) in enumerate(_AXES):
            self._sliders[i].setValue(int(default * 100))
            self._spinboxes[i].setValue(default)
        self._updating = False
        self._emit_pose()

    def set_target_values(
        self,
        x: float,
        y: float,
        z: float,
        roll: float,
        pitch: float,
        yaw: float,
    ) -> None:
        """Sett mål-sliders fra utenforstående kilde uten å emittere pose_changed.

        Brukes når mål-posen endres utenfra (f.eks. Home-kommando) slik at
        GUI-et viser samme målverdi uten å trigge en rundtur gjennom bridge.
        """
        self._updating = True
        for i, v in enumerate([x, y, z, roll, pitch, yaw]):
            self._spinboxes[i].setValue(v)
            self._sliders[i].setValue(int(v * 100))
        self._updating = False

    # ------------------------------------------------------------------
    # Navigable-implementasjon — styres av FocusManager.
    # nav_vertical bytter mellom de 6 aksene, nav_horizontal nudger
    # aktiv akse via spinbox-stegstørrelse.
    # ------------------------------------------------------------------

    def set_focused(self, focused: bool) -> None:
        """Markeres som fokusert; fremhev aktiv akse hvis ja."""
        if focused:
            self._highlight_active_axis()
        else:
            self._clear_axis_highlight()

    def set_edit_mode(self, edit: bool) -> None:
        """Når i edit-mode skal aktiv akse fortsatt være fremhevet."""
        if edit:
            self._highlight_active_axis()
        else:
            self._clear_axis_highlight()

    def nav_vertical(self, delta: int) -> None:
        """Bla mellom de 6 aksene."""
        self._active_axis_index = (self._active_axis_index + delta) % len(_AXES)
        self._highlight_active_axis()

    def nav_horizontal(self, delta: int) -> None:
        """Nudge aktiv akse med ett spinbox-steg."""
        spin = self._spinboxes[self._active_axis_index]
        spin.setValue(spin.value() + delta * spin.singleStep())

    def _highlight_active_axis(self) -> None:
        for i, lbl in enumerate(self._axis_labels):
            if i == self._active_axis_index:
                lbl.setStyleSheet(
                    "font-size: 13px; font-weight: 700; color: #f39c12;"
                )
            else:
                lbl.setStyleSheet("font-size: 13px; font-weight: 600;")

    def _clear_axis_highlight(self) -> None:
        for lbl in self._axis_labels:
            lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
