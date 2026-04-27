"""
pid_tuning_tab.py · Tab 3: PID-tuning.

6 PID-kort (X/Y/Z/Roll/Pitch/Yaw) med individuelle Kp/Ki/Kd-sliders,
sanntids feil-visning, og felles step-respons-graf.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...config.platform_config import Axis, PIDGains
from ..bridge.controller_bridge import ControllerBridge
from ..bridge.state_snapshot import StateSnapshot
from ..widgets.pid_card import PidCard
from ..widgets.realtime_plot import RealtimePlot


# Aksenavn og enheter
_AXIS_INFO = [
    (Axis.X, "X", "mm", 10.0, 5.0, 1.0),
    (Axis.Y, "Y", "mm", 10.0, 5.0, 1.0),
    (Axis.Z, "Z", "mm", 10.0, 5.0, 1.0),
    (Axis.ROLL, "Roll", "°", 5.0, 2.0, 0.5),
    (Axis.PITCH, "Pitch", "°", 5.0, 2.0, 0.5),
    (Axis.YAW, "Yaw", "°", 3.0, 1.0, 0.3),
]


class PidTuningTab(QWidget):
    """PID-tuning-fane med 6 kort og responsgrafer."""

    def __init__(self, bridge: ControllerBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._cards: dict[Axis, PidCard] = {}
        self._build_ui()
        self._load_gains_from_bridge()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # --- Venstre: 6 PID-kort i 3x2 grid ---
        left = QVBoxLayout()
        left.setSpacing(8)

        cards_box = QGroupBox("PID-parametere")
        grid = QGridLayout(cards_box)
        grid.setSpacing(8)

        for i, (axis, name, unit, kp_max, ki_max, kd_max) in enumerate(_AXIS_INFO):
            card = PidCard(name, unit, kp_max, ki_max, kd_max)
            card.gains_changed.connect(lambda gains, ax=axis: self._on_gains_changed(ax, gains))
            row, col = divmod(i, 2)
            grid.addWidget(card, row, col)
            self._cards[axis] = card

        left.addWidget(cards_box)
        root.addLayout(left, 3)

        # --- Høyre: grafer + kontroller ---
        right = QVBoxLayout()
        right.setSpacing(12)

        # Feilgraf — alle 6 akser i sanntid
        err_box = QGroupBox("PID-feil (sanntid)")
        eg = QVBoxLayout(err_box)

        series = ["X", "Y", "Z", "Roll", "Pitch", "Yaw"]
        self._error_plot = RealtimePlot(
            series_names=series,
            window_size=200,
            y_label="Feil",
            lock_y=True,
        )
        self._error_plot.setMinimumHeight(220)
        eg.addWidget(self._error_plot)

        # Kontrollrad: aksevalg + tidsvindu
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)
        ctrl.addWidget(QLabel("Vis:"))

        self._axis_checks: list[QCheckBox] = []
        for i, name in enumerate(series):
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.toggled.connect(
                lambda checked, idx=i: self._error_plot.set_series_visible(idx, checked)
            )
            ctrl.addWidget(cb)
            self._axis_checks.append(cb)

        ctrl.addSpacing(12)
        btn_all = QPushButton("Alle")
        btn_all.setFixedWidth(48)
        btn_all.clicked.connect(lambda: self._set_all_axes(True))
        ctrl.addWidget(btn_all)
        btn_none = QPushButton("Ingen")
        btn_none.setFixedWidth(52)
        btn_none.clicked.connect(lambda: self._set_all_axes(False))
        ctrl.addWidget(btn_none)

        ctrl.addStretch()
        ctrl.addWidget(QLabel("Tidsvindu:"))
        self._window_combo = QComboBox()
        for label, samples in [
            ("5 s", 100),
            ("10 s", 200),
            ("20 s", 400),
            ("60 s", 1200),
        ]:
            self._window_combo.addItem(label, samples)
        self._window_combo.setCurrentIndex(1)  # 10 s som standard
        self._window_combo.currentIndexChanged.connect(self._on_window_changed)
        ctrl.addWidget(self._window_combo)

        eg.addLayout(ctrl)

        hint = QLabel(
            "Rull med musehjulet over grafen for å zoome langs tidsaksen. "
            "Y-aksen auto-skaleres til valgte serier."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 10px; color: #888;")
        eg.addWidget(hint)

        right.addWidget(err_box, 1)

        # Step-respons kontroller
        step_box = QGroupBox("Step-respons")
        sbl = QVBoxLayout(step_box)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        ctrl_row.addWidget(QLabel("Akse:"))
        self._axis_combo = QComboBox()
        for axis, name, *_ in _AXIS_INFO:
            self._axis_combo.addItem(name, axis)
        ctrl_row.addWidget(self._axis_combo)

        ctrl_row.addWidget(QLabel("Steg:"))
        self._step_spin = QDoubleSpinBox()
        self._step_spin.setRange(0.1, 20.0)
        self._step_spin.setValue(5.0)
        self._step_spin.setSingleStep(0.5)
        self._step_spin.setFixedWidth(70)
        ctrl_row.addWidget(self._step_spin)

        self._step_btn = QPushButton("Trigger step")
        self._step_btn.clicked.connect(self._on_trigger_step)
        ctrl_row.addWidget(self._step_btn)

        ctrl_row.addStretch()
        sbl.addLayout(ctrl_row)

        # Info-tekst
        info = QLabel(
            "Step-respons sender et steg-signal på valgt akse og "
            "viser responskurven. Brukes til å tune PID-parametere."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 10px; color: #888;")
        sbl.addWidget(info)

        right.addWidget(step_box)
        right.addStretch()

        root.addLayout(right, 2)

    def _load_gains_from_bridge(self) -> None:
        """Last PID-gains fra bridge ved oppstart."""
        snapshot = self._bridge.get_snapshot()
        for axis, card in self._cards.items():
            if axis in snapshot.pid_gains:
                card.set_gains(snapshot.pid_gains[axis])

    def _on_gains_changed(self, axis: Axis, gains: PIDGains) -> None:
        """Bruker endret PID-parameter — send til bridge."""
        self._bridge.set_pid_gains(axis, gains)

    def _set_all_axes(self, visible: bool) -> None:
        """Slå alle aksevalg-checkbokser av eller på."""
        for cb in self._axis_checks:
            cb.setChecked(visible)

    @Slot(int)
    def _on_window_changed(self, _index: int) -> None:
        """Bytt tidsvindu på feilgrafen."""
        size = self._window_combo.currentData()
        if size is not None:
            self._error_plot.set_window_size(int(size))

    @Slot()
    def _on_trigger_step(self) -> None:
        """Trigger step-respons-test."""
        axis = self._axis_combo.currentData()
        step_size = self._step_spin.value()
        # For nå — juster mål-pose med et steg på valgt akse
        snapshot = self._bridge.get_snapshot()
        tgt = snapshot.target_pose

        from ...geometry.pose import Pose
        from ...geometry.vector3 import Vector3

        tx, ty, tz = tgt.translation.x, tgt.translation.y, tgt.translation.z
        rx, ry, rz = tgt.rotation.x, tgt.rotation.y, tgt.rotation.z

        if axis == Axis.X:
            tx += step_size
        elif axis == Axis.Y:
            ty += step_size
        elif axis == Axis.Z:
            tz += step_size
        elif axis == Axis.ROLL:
            rx += step_size
        elif axis == Axis.PITCH:
            ry += step_size
        elif axis == Axis.YAW:
            rz += step_size

        new_pose = Pose(
            translation=Vector3(tx, ty, tz),
            rotation=Vector3(rx, ry, rz),
        )
        self._bridge.set_target_pose(new_pose)

    def get_navigables(self) -> list:
        """Returner alle PID-kort som fokuserbare widgets, i akse-rekkefølge."""
        return [self._cards[axis] for axis, *_ in _AXIS_INFO if axis in self._cards]

    def update_from_snapshot(self, snapshot: StateSnapshot) -> None:
        """Oppdater kort-feilvisning og grafer."""
        # Oppdater PID-feil på kortene
        errors = snapshot.pid_errors
        error_values = []
        for axis, card in self._cards.items():
            err = errors.get(axis, 0.0)
            card.set_error(err)
            error_values.append(err)

        # Oppdater feilgraf
        self._error_plot.append_values(error_values)
        self._error_plot.refresh()

        # Synkroniser gains fra snapshot hvis de er endret eksternt
        for axis, card in self._cards.items():
            if axis in snapshot.pid_gains:
                current = card.get_gains()
                remote = snapshot.pid_gains[axis]
                if (abs(current.kp - remote.kp) > 0.001
                        or abs(current.ki - remote.ki) > 0.001
                        or abs(current.kd - remote.kd) > 0.001):
                    card.set_gains(remote)
