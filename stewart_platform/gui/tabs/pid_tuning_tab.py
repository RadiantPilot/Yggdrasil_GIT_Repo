"""
pid_tuning_tab.py · PID-tuning og mål-orientering.

Viser 3 PID-kort (Roll/Pitch/Yaw), 3 sliders for mål-orientering
og en sanntids feilgraf. Etter at translasjon ble fjernet fra
plattformen er dette eneste stedet brukeren kan styre mål-pose.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ...config.platform_config import Axis, PIDGains
from ...geometry.pose import Pose
from ...geometry.vector3 import Vector3
from ..bridge.controller_bridge import ControllerBridge
from ..bridge.state_snapshot import StateSnapshot
from ..widgets.pid_card import PidCard
from ..widgets.realtime_plot import RealtimePlot


# (Akse, navn, kp_max, ki_max, kd_max, slider_min, slider_max)
_AXES = [
    (Axis.ROLL,  "Roll",  5.0, 2.0, 0.5, -20.0, 20.0),
    (Axis.PITCH, "Pitch", 5.0, 2.0, 0.5, -20.0, 20.0),
    (Axis.YAW,   "Yaw",   3.0, 1.0, 0.3, -25.0, 25.0),
]


class _RotationSliders(QWidget):
    """Tre sliders + spinbokser for å sette mål-orientering."""

    rotation_changed = Signal(object)  # Vector3

    def __init__(self) -> None:
        super().__init__()
        self._sliders: list[QSlider] = []
        self._spins: list[QDoubleSpinBox] = []
        self._labels: list[QLabel] = []
        self._updating = False
        self._active_axis = 0

        grid = QGridLayout(self)
        grid.setSpacing(6)
        for col, hdr in enumerate(["Akse", "Mål", "Input", "Nå"]):
            lbl = QLabel(hdr)
            lbl.setStyleSheet("font-size: 10px; color: #888;")
            grid.addWidget(lbl, 0, col)

        for i, (_, name, *_, mn, mx) in enumerate(_AXES):
            row = i + 1
            lbl = QLabel(f"{name} (°)")
            lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
            grid.addWidget(lbl, row, 0)
            self._labels.append(lbl)

            slider = QSlider(Qt.Horizontal)
            slider.setRange(int(mn * 100), int(mx * 100))
            slider.setValue(0)
            slider.setProperty("axis_index", i)
            slider.valueChanged.connect(self._on_slider)
            grid.addWidget(slider, row, 1)
            self._sliders.append(slider)

            spin = QDoubleSpinBox()
            spin.setRange(mn, mx)
            spin.setDecimals(2)
            spin.setSingleStep(0.5)
            spin.setSuffix(" °")
            spin.setFixedWidth(90)
            spin.setProperty("axis_index", i)
            spin.valueChanged.connect(self._on_spin)
            grid.addWidget(spin, row, 2)
            self._spins.append(spin)

            cur = QLabel("—")
            cur.setStyleSheet("font-family: monospace; font-size: 11px; color: #888;")
            cur.setFixedWidth(60)
            cur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(cur, row, 3)

        self._current_labels = [grid.itemAtPosition(i + 1, 3).widget() for i in range(3)]

    def _on_slider(self, value: int) -> None:
        if self._updating:
            return
        idx = self.sender().property("axis_index")
        self._updating = True
        self._spins[idx].setValue(value / 100.0)
        self._updating = False
        self._emit()

    def _on_spin(self, value: float) -> None:
        if self._updating:
            return
        idx = self.sender().property("axis_index")
        self._updating = True
        self._sliders[idx].setValue(int(value * 100))
        self._updating = False
        self._emit()

    def _emit(self) -> None:
        rot = Vector3(
            self._spins[0].value(),
            self._spins[1].value(),
            self._spins[2].value(),
        )
        self.rotation_changed.emit(rot)

    def set_target(self, rotation: Vector3) -> None:
        """Sett slider-verdier uten å emittere signal."""
        self._updating = True
        for i, v in enumerate([rotation.x, rotation.y, rotation.z]):
            self._spins[i].setValue(v)
            self._sliders[i].setValue(int(v * 100))
        self._updating = False

    def update_current(self, rotation: Vector3) -> None:
        """Oppdater 'Nå'-kolonnen."""
        for i, v in enumerate([rotation.x, rotation.y, rotation.z]):
            self._current_labels[i].setText(f"{v:+.2f}")

    def set_target_and_emit(self, rotation: Vector3) -> None:
        """Sett slider-verdier og emitter signal."""
        self.set_target(rotation)
        self._emit()

    def reset_to_zero(self) -> None:
        """Sett alle akser til 0."""
        self._updating = True
        for i in range(3):
            self._sliders[i].setValue(0)
            self._spins[i].setValue(0.0)
        self._updating = False
        self._emit()

    # --- Knappenavigasjon (Navigable) ---

    def set_focused(self, focused: bool) -> None:
        if focused:
            self._highlight()
        else:
            self._clear_highlight()

    def set_edit_mode(self, edit: bool) -> None:
        if edit:
            self._highlight()
        else:
            self._clear_highlight()

    def nav_vertical(self, delta: int) -> None:
        self._active_axis = (self._active_axis + delta) % 3
        self._highlight()

    def nav_horizontal(self, delta: int) -> None:
        spin = self._spins[self._active_axis]
        spin.setValue(spin.value() + delta * spin.singleStep())

    def _highlight(self) -> None:
        for i, lbl in enumerate(self._labels):
            if i == self._active_axis:
                lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #f39c12;")
            else:
                lbl.setStyleSheet("font-size: 13px; font-weight: 600;")

    def _clear_highlight(self) -> None:
        for lbl in self._labels:
            lbl.setStyleSheet("font-size: 13px; font-weight: 600;")


class PidTuningTab(QWidget):
    """PID-tuning + mål-orienteringsstyring i samme fane."""

    def __init__(self, bridge: ControllerBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._cards: dict[Axis, PidCard] = {}
        self._build_ui()
        self._load_gains_from_bridge()
        self._bridge.target_pose_changed.connect(self._on_external_target_pose)

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # Venstre kolonne: PID-kort + målorientering
        left = QVBoxLayout()
        left.setSpacing(8)

        cards_box = QGroupBox("PID per akse")
        cards_layout = QHBoxLayout(cards_box)
        cards_layout.setSpacing(8)
        for axis, name, kp_max, ki_max, kd_max, *_ in _AXES:
            card = PidCard(name, "°", kp_max, ki_max, kd_max)
            card.gains_changed.connect(
                lambda gains, ax=axis: self._on_gains_changed(ax, gains)
            )
            cards_layout.addWidget(card)
            self._cards[axis] = card
        left.addWidget(cards_box)

        target_box = QGroupBox("Mål-orientering")
        tl = QVBoxLayout(target_box)
        self._sliders = _RotationSliders()
        self._sliders.rotation_changed.connect(self._on_target_changed)
        tl.addWidget(self._sliders)

        preset_row = QHBoxLayout()
        for label, callback in [
            ("Null", self._preset_zero),
            ("Roll +10°", lambda: self._preset_axis(0, 10.0)),
            ("Pitch +10°", lambda: self._preset_axis(1, 10.0)),
            ("Yaw +10°", lambda: self._preset_axis(2, 10.0)),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(callback)
            preset_row.addWidget(btn)
        preset_row.addStretch()
        tl.addLayout(preset_row)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 11px; color: #888;")
        tl.addWidget(self._status_label)

        left.addWidget(target_box)
        left.addStretch()
        root.addLayout(left, 3)

        # Høyre kolonne: Sanntids feilgraf
        right = QVBoxLayout()
        right.setSpacing(12)

        err_box = QGroupBox("PID-feil (sanntid)")
        eg = QVBoxLayout(err_box)
        # Fast Y-range matcher rotasjonsgrensene — feilen kan ikke
        # bli mye større enn ±max_rotation_deg uten å trigge safety.
        self._error_plot = RealtimePlot(
            series_names=["Roll", "Pitch", "Yaw"],
            window_size=120,
            y_label="Feil (°)",
            y_range=(-30.0, 30.0),
        )
        self._error_plot.setMinimumHeight(260)
        eg.addWidget(self._error_plot)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Vis:"))
        self._axis_checks: list[QCheckBox] = []
        for i, name in enumerate(["Roll", "Pitch", "Yaw"]):
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.toggled.connect(
                lambda checked, idx=i: self._error_plot.set_series_visible(idx, checked)
            )
            ctrl.addWidget(cb)
            self._axis_checks.append(cb)
        ctrl.addStretch()
        ctrl.addWidget(QLabel("Tidsvindu:"))
        self._window_combo = QComboBox()
        # Antagelser: 8 Hz polling × samples = sekunder.
        for label, samples in [("5 s", 40), ("15 s", 120), ("30 s", 240), ("60 s", 480)]:
            self._window_combo.addItem(label, samples)
        self._window_combo.setCurrentIndex(1)
        self._window_combo.currentIndexChanged.connect(self._on_window_changed)
        ctrl.addWidget(self._window_combo)
        eg.addLayout(ctrl)

        right.addWidget(err_box, 1)
        root.addLayout(right, 2)

    # ------------------------------------------------------------------
    # Bridge-koblinger
    # ------------------------------------------------------------------

    def _load_gains_from_bridge(self) -> None:
        snapshot = self._bridge.get_snapshot()
        for axis, card in self._cards.items():
            if axis in snapshot.pid_gains:
                card.set_gains(snapshot.pid_gains[axis])

    def _on_gains_changed(self, axis: Axis, gains: PIDGains) -> None:
        self._bridge.set_pid_gains(axis, gains)

    @Slot(object)
    def _on_target_changed(self, rotation: Vector3) -> None:
        ok = self._bridge.set_target_pose(Pose(rotation=rotation))
        if not ok:
            self._status_label.setText("Mål avvist av sikkerhetsmonitor")
            self._status_label.setStyleSheet("font-size: 11px; color: #c53434;")
        else:
            self._status_label.setText("")

    @Slot(object)
    def _on_external_target_pose(self, pose: Pose) -> None:
        self._sliders.set_target(pose.rotation)

    # ------------------------------------------------------------------
    # Presets / kontroller
    # ------------------------------------------------------------------

    def _preset_zero(self) -> None:
        self._sliders.reset_to_zero()

    def _preset_axis(self, idx: int, value: float) -> None:
        rot = [0.0, 0.0, 0.0]
        rot[idx] = value
        self._sliders.set_target_and_emit(Vector3(*rot))

    @Slot(int)
    def _on_window_changed(self, _index: int) -> None:
        size = self._window_combo.currentData()
        if size is not None:
            self._error_plot.set_window_size(int(size))

    # ------------------------------------------------------------------
    # Snapshot-oppdatering + knappenavigasjon
    # ------------------------------------------------------------------

    def get_navigables(self) -> list:
        """PID-kortene + målorienterings-sliders for FocusManager."""
        return [self._cards[axis] for axis, *_ in _AXES] + [self._sliders]

    def update_from_snapshot(self, snapshot: StateSnapshot) -> None:
        """Oppdater feilkort og sanntidsgraf fra snapshot."""
        errors = snapshot.pid_errors
        values = []
        for axis, card in self._cards.items():
            err = errors.get(axis, 0.0)
            card.set_error(err)
            values.append(err)
        self._error_plot.append_values(values)

        # Synkroniser PID-kort hvis gains er endret eksternt
        for axis, card in self._cards.items():
            if axis in snapshot.pid_gains:
                local = card.get_gains()
                remote = snapshot.pid_gains[axis]
                if (abs(local.kp - remote.kp) > 0.001
                        or abs(local.ki - remote.ki) > 0.001
                        or abs(local.kd - remote.kd) > 0.001):
                    card.set_gains(remote)

        # Oppdater "Nå"-kolonne med målt orientering
        self._sliders.update_current(snapshot.current_pose.rotation)
