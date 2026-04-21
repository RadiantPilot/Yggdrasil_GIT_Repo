"""
overview_tab.py · Tab 1: Oversikt.

Samlebilde for raskt overblikk — statusbanner, nåværende/mål-pose,
IMU-sammendrag, servo-bargrafer og hendelseslogg.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..bridge.controller_bridge import ControllerBridge
from ..bridge.state_snapshot import StateSnapshot
from ..utils.formatting import fmt_deg, fmt_mm
from ..widgets.event_log import EventLog
from ..widgets.servo_bars import ServoBars
from ..widgets.status_banner import StatusBanner


class OverviewTab(QWidget):
    """Oversiktsfane — alt-på-ett-blikk dashboard."""

    def __init__(self, bridge: ControllerBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # --- Statusbanner ---
        self._banner = StatusBanner()
        root.addWidget(self._banner)

        # --- Midtre rad: pose + IMU + servoer ---
        mid = QHBoxLayout()
        mid.setSpacing(12)

        # Pose-boks
        pose_box = QGroupBox("Pose")
        pg = QGridLayout(pose_box)
        pg.setSpacing(4)

        lbl_style = "font-family: monospace; font-size: 11px;"
        header_style = "font-size: 10px; color: #888;"
        pg.addWidget(self._hdr("", header_style), 0, 0)
        pg.addWidget(self._hdr("Nå", header_style), 0, 1)
        pg.addWidget(self._hdr("Mål", header_style), 0, 2)

        self._pose_labels: list[tuple[QLabel, QLabel]] = []
        axes = [("X", "mm"), ("Y", "mm"), ("Z", "mm"),
                ("Roll", "°"), ("Pitch", "°"), ("Yaw", "°")]
        for i, (name, unit) in enumerate(axes):
            row = i + 1
            pg.addWidget(self._hdr(f"{name} ({unit})", "font-size: 11px; font-weight: 500;"), row, 0)
            cur = QLabel("—")
            cur.setStyleSheet(lbl_style)
            cur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tgt = QLabel("—")
            tgt.setStyleSheet(lbl_style)
            tgt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            pg.addWidget(cur, row, 1)
            pg.addWidget(tgt, row, 2)
            self._pose_labels.append((cur, tgt))

        mid.addWidget(pose_box, 1)

        # IMU-boks
        imu_box = QGroupBox("IMU (bunnplate)")
        ig = QGridLayout(imu_box)
        ig.setSpacing(4)

        self._imu_labels: dict[str, QLabel] = {}
        imu_fields = [
            ("Roll", "ori_roll"), ("Pitch", "ori_pitch"), ("Yaw", "ori_yaw"),
            ("Accel X", "ax"), ("Accel Y", "ay"), ("Accel Z", "az"),
            ("Gyro X", "gx"), ("Gyro Y", "gy"), ("Gyro Z", "gz"),
        ]
        for i, (name, key) in enumerate(imu_fields):
            ig.addWidget(self._hdr(name, "font-size: 11px;"), i, 0)
            lbl = QLabel("—")
            lbl.setStyleSheet(lbl_style)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ig.addWidget(lbl, i, 1)
            self._imu_labels[key] = lbl

        mid.addWidget(imu_box, 1)

        # Servo-boks
        servo_box = QGroupBox("Servoer")
        sl = QVBoxLayout(servo_box)
        self._servo_bars = ServoBars(min_angle=0.0, max_angle=180.0)
        sl.addWidget(self._servo_bars)

        mid.addWidget(servo_box, 1)
        root.addLayout(mid)

        # --- Hendelseslogg ---
        log_box = QGroupBox("Hendelser")
        ll = QVBoxLayout(log_box)
        self._event_log = EventLog(max_events=20)
        ll.addWidget(self._event_log)
        root.addWidget(log_box, 1)

    def _hdr(self, text: str, style: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        return lbl

    def update_from_snapshot(self, snapshot: StateSnapshot) -> None:
        """Oppdater alle felter fra snapshot."""
        # Banner
        if snapshot.is_e_stopped:
            self._banner.set_status(
                "error", "NØDSTOPP AKTIV",
                snapshot.e_stop_reason or "",
            )
        elif snapshot.is_running:
            self._banner.set_status(
                "running", "System kjører",
                f"{snapshot.loop_frequency_hz:.1f} Hz",
            )
        else:
            self._banner.set_status("stopped", "System stoppet", "")

        # Pose
        cur = snapshot.current_pose
        tgt = snapshot.target_pose
        cur_vals = [cur.translation.x, cur.translation.y, cur.translation.z,
                    cur.rotation.x, cur.rotation.y, cur.rotation.z]
        tgt_vals = [tgt.translation.x, tgt.translation.y, tgt.translation.z,
                    tgt.rotation.x, tgt.rotation.y, tgt.rotation.z]
        for i, (c_lbl, t_lbl) in enumerate(self._pose_labels):
            fmt = fmt_mm if i < 3 else fmt_deg
            c_lbl.setText(fmt(cur_vals[i]))
            t_lbl.setText(fmt(tgt_vals[i]))

        # IMU
        a = snapshot.imu_acceleration
        g = snapshot.imu_angular_velocity
        o = snapshot.imu_orientation
        self._imu_labels["ori_roll"].setText(f"{o[0]:+.2f}°")
        self._imu_labels["ori_pitch"].setText(f"{o[1]:+.2f}°")
        self._imu_labels["ori_yaw"].setText(f"{o[2]:+.2f}°")
        self._imu_labels["ax"].setText(f"{a.x:+.3f} m/s²")
        self._imu_labels["ay"].setText(f"{a.y:+.3f} m/s²")
        self._imu_labels["az"].setText(f"{a.z:+.3f} m/s²")
        self._imu_labels["gx"].setText(f"{g.x:+.2f} °/s")
        self._imu_labels["gy"].setText(f"{g.y:+.2f} °/s")
        self._imu_labels["gz"].setText(f"{g.z:+.2f} °/s")

        # Servoer
        self._servo_bars.update_angles(snapshot.servo_angles)

        # Hendelseslogg — oppdater fra bridge-events
        events = self._bridge.get_events()
        # Bare legg til nye hendelser (sjekk om loggen er synkronisert)
        current_count = len(self._event_log._events)
        if len(events) > current_count:
            for ev in reversed(events[current_count:]):
                self._event_log.add_event(ev.level, ev.message)
