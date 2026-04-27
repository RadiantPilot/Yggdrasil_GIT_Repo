"""
pose_control_tab.py · Tab 2: Pose-kontroll.

Manuell 6-DOF posekontroll med sliders, numerisk input,
nåværende-pose-visning og preset-knapper.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...config.platform_config import Axis
from ...geometry.pose import Pose
from ...geometry.vector3 import Vector3
from ..bridge.controller_bridge import ControllerBridge
from ..bridge.state_snapshot import StateSnapshot
from ..utils.formatting import fmt_deg, fmt_mm
from ..widgets.pose_sliders import PoseSliders
from ..widgets.servo_bars import ServoBars


class PoseControlTab(QWidget):
    """Pose-kontroll-fane med 6-DOF sliders og presets."""

    def __init__(self, bridge: ControllerBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._build_ui()
        # Synkroniser sliders når mål-pose endres utenfra (f.eks. Home-knapp)
        self._bridge.target_pose_changed.connect(self._on_external_target_pose)

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # --- Venstre kolonne: Sliders + presets ---
        left = QVBoxLayout()
        left.setSpacing(12)

        # Slider-panel
        slider_box = QGroupBox("Mål-pose")
        sl = QVBoxLayout(slider_box)
        self._sliders = PoseSliders()
        self._sliders.pose_changed.connect(self._on_pose_changed)
        sl.addWidget(self._sliders)
        left.addWidget(slider_box)

        # Presets
        preset_box = QGroupBox("Presets")
        pl = QHBoxLayout(preset_box)
        pl.setSpacing(8)

        presets = [
            ("Home", self._preset_home),
            ("Flat", self._preset_flat),
            ("Tilt +10°", self._preset_tilt_pos),
            ("Tilt -10°", self._preset_tilt_neg),
            ("Opp +5mm", self._preset_up),
        ]
        for label, callback in presets:
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.clicked.connect(callback)
            pl.addWidget(btn)

        left.addWidget(preset_box)
        left.addStretch()

        root.addLayout(left, 2)

        # --- Høyre kolonne: Status + servoer ---
        right = QVBoxLayout()
        right.setSpacing(12)

        # Nåværende pose
        cur_box = QGroupBox("Nåværende pose")
        cg = QGridLayout(cur_box)
        cg.setSpacing(4)

        lbl_style = "font-family: monospace; font-size: 12px;"
        hdr_style = "font-size: 10px; color: #888;"
        cg.addWidget(self._mk_label("", hdr_style), 0, 0)
        cg.addWidget(self._mk_label("Nå", hdr_style), 0, 1)
        cg.addWidget(self._mk_label("Mål", hdr_style), 0, 2)
        cg.addWidget(self._mk_label("Diff", hdr_style), 0, 3)

        self._pose_rows: list[tuple[QLabel, QLabel, QLabel]] = []
        axes = [("X", "mm"), ("Y", "mm"), ("Z", "mm"),
                ("Roll", "°"), ("Pitch", "°"), ("Yaw", "°")]
        for i, (name, unit) in enumerate(axes):
            row = i + 1
            cg.addWidget(self._mk_label(f"{name} ({unit})", "font-size: 11px; font-weight: 500;"), row, 0)
            cur = QLabel("—")
            cur.setStyleSheet(lbl_style)
            cur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tgt = QLabel("—")
            tgt.setStyleSheet(lbl_style)
            tgt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            diff = QLabel("—")
            diff.setStyleSheet(lbl_style)
            diff.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            cg.addWidget(cur, row, 1)
            cg.addWidget(tgt, row, 2)
            cg.addWidget(diff, row, 3)
            self._pose_rows.append((cur, tgt, diff))

        right.addWidget(cur_box)

        # Servo-visning
        servo_box = QGroupBox("Servovinkler")
        svl = QVBoxLayout(servo_box)
        self._servo_bars = ServoBars(min_angle=0.0, max_angle=180.0)
        svl.addWidget(self._servo_bars)
        right.addWidget(servo_box)

        # Status-linje
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 11px; color: #888;")
        right.addWidget(self._status_label)
        right.addStretch()

        root.addLayout(right, 1)

    def _mk_label(self, text: str, style: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        return lbl

    @Slot(object)
    def _on_external_target_pose(self, pose: Pose) -> None:
        """Mål-pose endret utenfra — speil verdiene inn i sliders."""
        self._sliders.set_target_values(
            pose.translation.x, pose.translation.y, pose.translation.z,
            pose.rotation.x, pose.rotation.y, pose.rotation.z,
        )

    @Slot(dict)
    def _on_pose_changed(self, values: dict) -> None:
        """Bruker endret en slider — send ny mål-pose til bridge."""
        pose = Pose(
            translation=Vector3(
                values.get("x", 0.0),
                values.get("y", 0.0),
                values.get("z", 25.0),
            ),
            rotation=Vector3(
                values.get("roll", 0.0),
                values.get("pitch", 0.0),
                values.get("yaw", 0.0),
            ),
        )
        ok = self._bridge.set_target_pose(pose)
        if not ok:
            self._status_label.setText("Pose avvist av sikkerhetsmonitor")
            self._status_label.setStyleSheet("font-size: 11px; color: #c53434;")
        else:
            self._status_label.setText("")

    def _preset_home(self) -> None:
        self._sliders.reset_to_home()

    def _preset_flat(self) -> None:
        self._sliders._updating = True
        for i, val in enumerate([0.0, 0.0, 25.0, 0.0, 0.0, 0.0]):
            self._sliders._sliders[i].setValue(int(val * 100))
            self._sliders._spinboxes[i].setValue(val)
        self._sliders._updating = False
        self._sliders._emit_pose()

    def _preset_tilt_pos(self) -> None:
        self._sliders._updating = True
        for i, val in enumerate([0.0, 0.0, 25.0, 10.0, 0.0, 0.0]):
            self._sliders._sliders[i].setValue(int(val * 100))
            self._sliders._spinboxes[i].setValue(val)
        self._sliders._updating = False
        self._sliders._emit_pose()

    def _preset_tilt_neg(self) -> None:
        self._sliders._updating = True
        for i, val in enumerate([0.0, 0.0, 25.0, -10.0, 0.0, 0.0]):
            self._sliders._sliders[i].setValue(int(val * 100))
            self._sliders._spinboxes[i].setValue(val)
        self._sliders._updating = False
        self._sliders._emit_pose()

    def _preset_up(self) -> None:
        self._sliders._updating = True
        for i, val in enumerate([0.0, 0.0, 30.0, 0.0, 0.0, 0.0]):
            self._sliders._sliders[i].setValue(int(val * 100))
            self._sliders._spinboxes[i].setValue(val)
        self._sliders._updating = False
        self._sliders._emit_pose()

    def get_navigables(self) -> list:
        """Returner widgets som FocusManager kan styre med knappekortet."""
        return [self._sliders]

    def update_from_snapshot(self, snapshot: StateSnapshot) -> None:
        """Oppdater nåværende-pose-visning og servobars."""
        cur = snapshot.current_pose
        tgt = snapshot.target_pose

        cur_vals = [cur.translation.x, cur.translation.y, cur.translation.z,
                    cur.rotation.x, cur.rotation.y, cur.rotation.z]
        tgt_vals = [tgt.translation.x, tgt.translation.y, tgt.translation.z,
                    tgt.rotation.x, tgt.rotation.y, tgt.rotation.z]

        for i, (c_lbl, t_lbl, d_lbl) in enumerate(self._pose_rows):
            fmt = fmt_mm if i < 3 else fmt_deg
            c_lbl.setText(fmt(cur_vals[i]))
            t_lbl.setText(fmt(tgt_vals[i]))
            diff = tgt_vals[i] - cur_vals[i]
            d_lbl.setText(fmt(diff))
            # Fargekode diff
            if abs(diff) > 2.0:
                d_lbl.setStyleSheet("font-family: monospace; font-size: 12px; color: #c53434;")
            elif abs(diff) > 0.5:
                d_lbl.setStyleSheet("font-family: monospace; font-size: 12px; color: #d4a017;")
            else:
                d_lbl.setStyleSheet("font-family: monospace; font-size: 12px; color: #4a9a3c;")

        # Oppdater "Nå"-kolonne i sliders
        self._sliders.update_current(
            cur.translation.x, cur.translation.y, cur.translation.z,
            cur.rotation.x, cur.rotation.y, cur.rotation.z,
        )

        self._servo_bars.update_angles(snapshot.servo_angles)
