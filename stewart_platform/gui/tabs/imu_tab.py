"""
imu_tab.py · Tab 4: IMU.

Sanntids akselerasjon- og gyro-grafer (3-akser), orientering,
kalibrerings-knapper og sensorinfo.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..bridge.controller_bridge import CalibrationResult, ControllerBridge
from ..bridge.state_snapshot import StateSnapshot
from ..widgets.realtime_plot import RealtimePlot


class _CalibrationThread(QThread):
    """Kjører gyro- eller akselerometer-kalibrering uten å blokkere GUI-tråden."""
    finished = Signal(str, object)  # (sensor-navn, CalibrationResult)

    def __init__(self, bridge: ControllerBridge, cal_type: str) -> None:
        super().__init__()
        self._bridge = bridge
        self._cal_type = cal_type

    def run(self) -> None:
        if self._cal_type == "gyro":
            result = self._bridge.calibrate_gyro()
            self.finished.emit("Gyro", result)
        else:
            result = self._bridge.calibrate_accelerometer()
            self.finished.emit("Akselerometer", result)


class ImuTab(QWidget):
    """IMU-fane med sanntidsgrafer og kalibrering."""

    def __init__(self, bridge: ControllerBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._cal_thread: _CalibrationThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # --- Øvre rad: orientering + kalibrering ---
        # Accel og gyro vises kun som tall i kalibreringsboksens rå-grid;
        # plattformen styres rotasjonelt og bevegelseshistorikk for de
        # andre aksene tilfører ikke verdi for tuning.
        lower = QHBoxLayout()
        lower.setSpacing(12)

        # Orientering
        ori_box = QGroupBox("Orientering (fusjon)")
        # Merk: ingen parent her — vi monterer `og` inn i `ori_layout`
        # under, og setter `ori_layout` som boks-layout. Hvis vi sender
        # ori_box inn i konstruktøren får `og` to parents og Qt logger
        # "QLayout::addChildLayout: layout QGridLayout already has a parent".
        og = QGridLayout()
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

        # Orienterings-graf — fast Y-range matcher safety_config.max_rotation_deg
        # invert_x=True: nyeste data vises til venstre (som et rullende vindu)
        self._ori_plot = RealtimePlot(
            series_names=["Roll", "Pitch", "Yaw"],
            window_size=120,
            y_label="°",
            y_range=(-30.0, 30.0),
            invert_x=True,
        )
        self._ori_plot.setMinimumHeight(180)
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

    def _start_calibration(self, cal_type: str) -> None:
        """Start kalibrering i bakgrunnstråd — ikke-blokkerende."""
        if self._cal_thread is not None and self._cal_thread.isRunning():
            return
        self._btn_gyro.setEnabled(False)
        self._btn_accel.setEnabled(False)
        label = "Gyro" if cal_type == "gyro" else "Akselerometer"
        self._cal_status.setText(f"{label}-kalibrering kjører — hold plattformen stille...")
        self._cal_status.setStyleSheet("font-size: 10px; color: #888;")

        self._cal_thread = _CalibrationThread(self._bridge, cal_type)
        self._cal_thread.finished.connect(self._on_cal_done)
        self._cal_thread.finished.connect(self._cal_thread.deleteLater)
        self._cal_thread.start()

    @Slot()
    def _on_cal_gyro(self) -> None:
        self._start_calibration("gyro")

    @Slot()
    def _on_cal_accel(self) -> None:
        self._start_calibration("accel")

    @Slot(str, object)
    def _on_cal_done(self, name: str, result: object) -> None:
        self._btn_gyro.setEnabled(True)
        self._btn_accel.setEnabled(True)
        self._show_cal_result(name, result)

    def _show_cal_result(self, name: str, result: CalibrationResult) -> None:
        """Vis resultat av kalibrering med farge som matcher utfallet."""
        if result is CalibrationResult.OK:
            suffix = " (mock)" if self._bridge.is_mock else ""
            msg = f"{name}-kalibrering fullført{suffix}"
            color = "#4a9a3c"
        elif result is CalibrationResult.NOT_IMPL:
            msg = f"{name}-kalibrering er ikke implementert i driveren enda"
            color = "#d4a017"
        elif result is CalibrationResult.NOT_READY:
            msg = f"{name}-kalibrering krever at IMU er tilkoblet"
            color = "#d4a017"
        else:
            msg = f"{name}-kalibrering feilet — se hendelseslogg"
            color = "#c53434"
        self._cal_status.setText(msg)
        self._cal_status.setStyleSheet(f"font-size: 10px; color: {color};")

    def update_from_snapshot(self, snapshot: StateSnapshot) -> None:
        """Oppdater grafer og verdier fra snapshot."""
        a = snapshot.imu_acceleration
        g = snapshot.imu_angular_velocity
        o = snapshot.imu_orientation

        # Orientering
        self._ori_labels["roll"].setText(f"{o[0]:+.2f}°")
        self._ori_labels["pitch"].setText(f"{o[1]:+.2f}°")
        self._ori_labels["yaw"].setText(f"{o[2]:+.2f}°")

        self._ori_plot.append_values([o[0], o[1], o[2]])

        # Råverdier
        self._raw_labels["accel_x"].setText(f"{a.x:+.4f}")
        self._raw_labels["accel_y"].setText(f"{a.y:+.4f}")
        self._raw_labels["accel_z"].setText(f"{a.z:+.4f}")
        self._raw_labels["gyro_x"].setText(f"{g.x:+.4f}")
        self._raw_labels["gyro_y"].setText(f"{g.y:+.4f}")
        self._raw_labels["gyro_z"].setText(f"{g.z:+.4f}")
