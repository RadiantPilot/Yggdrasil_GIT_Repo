"""
imu_tab.py · Tab 4: IMU.

Sanntids akselerasjon- og gyro-grafer (3-akser), orientering,
kalibrerings-knapper og sensorinfo.
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

from ..bridge.controller_bridge import ControllerBridge
from ..bridge.state_snapshot import StateSnapshot
from ..widgets.realtime_plot import RealtimePlot


class ImuTab(QWidget):
    """IMU-fane med sanntidsgrafer og kalibrering."""

    def __init__(self, bridge: ControllerBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # --- Øverste rad: tre grafer ---
        graphs = QHBoxLayout()
        graphs.setSpacing(12)

        # Akselerasjon
        accel_box = QGroupBox("Akselerasjon (m/s²)")
        al = QVBoxLayout(accel_box)
        self._accel_plot = RealtimePlot(
            series_names=["X", "Y", "Z"],
            window_size=200,
            y_label="m/s²",
        )
        self._accel_plot.setMinimumHeight(180)
        al.addWidget(self._accel_plot)
        graphs.addWidget(accel_box)

        # Gyroskop
        gyro_box = QGroupBox("Gyroskop (°/s)")
        gl = QVBoxLayout(gyro_box)
        self._gyro_plot = RealtimePlot(
            series_names=["X", "Y", "Z"],
            window_size=200,
            y_label="°/s",
        )
        self._gyro_plot.setMinimumHeight(180)
        gl.addWidget(self._gyro_plot)
        graphs.addWidget(gyro_box)

        root.addLayout(graphs, 2)

        # --- Nedre rad: orientering + kalibrering ---
        lower = QHBoxLayout()
        lower.setSpacing(12)

        # Orientering
        ori_box = QGroupBox("Orientering (fusjon)")
        og = QGridLayout(ori_box)
        og.setSpacing(8)

        lbl_style = "font-family: monospace; font-size: 14px;"
        self._ori_labels: dict[str, QLabel] = {}
        for i, name in enumerate(["Roll", "Pitch", "Yaw"]):
            og.addWidget(self._mk_label(name, "font-size: 12px; font-weight: 500;"), i, 0)
            val = QLabel("—")
            val.setStyleSheet(lbl_style)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            og.addWidget(val, i, 1)
            self._ori_labels[name.lower()] = val

        # Orienterings-graf
        self._ori_plot = RealtimePlot(
            series_names=["Roll", "Pitch", "Yaw"],
            window_size=200,
            y_label="°",
        )
        self._ori_plot.setMinimumHeight(120)
        ori_layout = QVBoxLayout()
        ori_layout.addLayout(og)
        ori_layout.addWidget(self._ori_plot)
        ori_box.setLayout(ori_layout)

        lower.addWidget(ori_box, 2)

        # Kalibrering og info
        cal_box = QGroupBox("Kalibrering og info")
        cl = QVBoxLayout(cal_box)
        cl.setSpacing(12)

        # Sensor-info
        info_grid = QGridLayout()
        info_grid.setSpacing(4)
        info_fields = [
            ("Sensor", "LSM6DSOXTR"),
            ("Buss", "I2C"),
            ("Plassering", "Bunnplate"),
        ]
        for i, (name, val) in enumerate(info_fields):
            info_grid.addWidget(self._mk_label(name, "font-size: 11px; color: #666;"), i, 0)
            info_grid.addWidget(self._mk_label(val, "font-size: 11px;"), i, 1)
        cl.addLayout(info_grid)

        # Råverdier
        raw_grid = QGridLayout()
        raw_grid.setSpacing(4)
        raw_grid.addWidget(self._mk_label("", ""), 0, 0)
        raw_grid.addWidget(self._mk_label("X", "font-size: 10px; color: #888;"), 0, 1)
        raw_grid.addWidget(self._mk_label("Y", "font-size: 10px; color: #888;"), 0, 2)
        raw_grid.addWidget(self._mk_label("Z", "font-size: 10px; color: #888;"), 0, 3)

        self._raw_labels: dict[str, QLabel] = {}
        raw_style = "font-family: monospace; font-size: 11px;"
        for i, prefix in enumerate(["accel", "gyro"]):
            row = i + 1
            raw_grid.addWidget(self._mk_label(
                "Accel" if prefix == "accel" else "Gyro",
                "font-size: 11px; font-weight: 500;",
            ), row, 0)
            for j, comp in enumerate(["x", "y", "z"]):
                lbl = QLabel("—")
                lbl.setStyleSheet(raw_style)
                lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                raw_grid.addWidget(lbl, row, j + 1)
                self._raw_labels[f"{prefix}_{comp}"] = lbl

        cl.addLayout(raw_grid)

        # Kalibrerings-knapper
        cl.addSpacing(8)
        cal_label = QLabel("Kalibrering")
        cal_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        cl.addWidget(cal_label)

        cal_info = QLabel(
            "Hold plattformen stille og flat under kalibrering. "
            "Gyro-kalibrering tar ~2 sekunder."
        )
        cal_info.setWordWrap(True)
        cal_info.setStyleSheet("font-size: 10px; color: #888;")
        cl.addWidget(cal_info)

        btn_row = QHBoxLayout()
        self._btn_gyro = QPushButton("Kalibrer Gyro")
        self._btn_gyro.clicked.connect(self._on_cal_gyro)
        btn_row.addWidget(self._btn_gyro)

        self._btn_accel = QPushButton("Kalibrer Akselerometer")
        self._btn_accel.clicked.connect(self._on_cal_accel)
        btn_row.addWidget(self._btn_accel)

        cl.addLayout(btn_row)

        self._cal_status = QLabel("")
        self._cal_status.setStyleSheet("font-size: 10px; color: #4a9a3c;")
        cl.addWidget(self._cal_status)

        cl.addStretch()
        lower.addWidget(cal_box, 1)

        root.addLayout(lower, 1)

    def _mk_label(self, text: str, style: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        return lbl

    @Slot()
    def _on_cal_gyro(self) -> None:
        ok = self._bridge.calibrate_gyro()
        if ok:
            self._cal_status.setText("Gyro-kalibrering fullført")
            self._cal_status.setStyleSheet("font-size: 10px; color: #4a9a3c;")
        else:
            self._cal_status.setText("Gyro-kalibrering feilet")
            self._cal_status.setStyleSheet("font-size: 10px; color: #c53434;")

    @Slot()
    def _on_cal_accel(self) -> None:
        ok = self._bridge.calibrate_accelerometer()
        if ok:
            self._cal_status.setText("Akselerometer-kalibrering fullført")
            self._cal_status.setStyleSheet("font-size: 10px; color: #4a9a3c;")
        else:
            self._cal_status.setText("Akselerometer-kalibrering feilet")
            self._cal_status.setStyleSheet("font-size: 10px; color: #c53434;")

    def update_from_snapshot(self, snapshot: StateSnapshot) -> None:
        """Oppdater grafer og verdier fra snapshot."""
        a = snapshot.imu_acceleration
        g = snapshot.imu_angular_velocity
        o = snapshot.imu_orientation

        # Akselerasjon-graf
        self._accel_plot.append_values([a.x, a.y, a.z])
        self._accel_plot.refresh()

        # Gyro-graf
        self._gyro_plot.append_values([g.x, g.y, g.z])
        self._gyro_plot.refresh()

        # Orientering
        self._ori_labels["roll"].setText(f"{o[0]:+.2f}°")
        self._ori_labels["pitch"].setText(f"{o[1]:+.2f}°")
        self._ori_labels["yaw"].setText(f"{o[2]:+.2f}°")

        self._ori_plot.append_values([o[0], o[1], o[2]])
        self._ori_plot.refresh()

        # Råverdier
        self._raw_labels["accel_x"].setText(f"{a.x:+.4f}")
        self._raw_labels["accel_y"].setText(f"{a.y:+.4f}")
        self._raw_labels["accel_z"].setText(f"{a.z:+.4f}")
        self._raw_labels["gyro_x"].setText(f"{g.x:+.4f}")
        self._raw_labels["gyro_y"].setText(f"{g.y:+.4f}")
        self._raw_labels["gyro_z"].setText(f"{g.z:+.4f}")
