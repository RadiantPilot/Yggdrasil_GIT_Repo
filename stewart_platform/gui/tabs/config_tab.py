"""
config_tab.py · Tab 5: Konfigurasjon.

Redigerbar plattformkonfigurasjon: geometri, I2C-adresser,
servotabell, og valider/lagre-knapper.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...config.platform_config import PlatformConfig, ServoConfig
from ..bridge.controller_bridge import ControllerBridge
from ..bridge.state_snapshot import StateSnapshot


class ConfigTab(QWidget):
    """Konfigurasjonsfane med redigerbare parametere."""

    def __init__(self, bridge: ControllerBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # --- Øvre rad: geometri + I2C ---
        upper = QHBoxLayout()
        upper.setSpacing(12)

        # Geometri
        geo_box = QGroupBox("Plattformgeometri")
        gg = QGridLayout(geo_box)
        gg.setSpacing(6)

        self._geo_spins: dict[str, QDoubleSpinBox] = {}
        geo_fields = [
            ("base_radius", "Bunnradius (mm)", 10.0, 500.0, 1.0),
            ("platform_radius", "Plattformradius (mm)", 10.0, 500.0, 1.0),
            ("servo_horn_length", "Servoarm (mm)", 5.0, 100.0, 0.5),
            ("rod_length", "Staglengde (mm)", 50.0, 500.0, 1.0),
            ("home_height", "Hvilehøyde (mm)", 20.0, 300.0, 1.0),
        ]
        for i, (key, label, mn, mx, step) in enumerate(geo_fields):
            gg.addWidget(QLabel(label), i, 0)
            spin = QDoubleSpinBox()
            spin.setRange(mn, mx)
            spin.setSingleStep(step)
            spin.setDecimals(1)
            spin.setFixedWidth(100)
            gg.addWidget(spin, i, 1)
            self._geo_spins[key] = spin

        upper.addWidget(geo_box)

        # I2C-innstillinger
        i2c_box = QGroupBox("I2C-innstillinger")
        ig = QGridLayout(i2c_box)
        ig.setSpacing(6)

        self._i2c_spins: dict[str, QSpinBox] = {}
        i2c_fields = [
            ("i2c_bus_number", "Buss-nummer", 0, 10),
            ("pca9685_address", "PCA9685 adresse", 0, 127),
            ("pca9685_frequency", "PWM frekvens (Hz)", 24, 1526),
            ("lsm6dsox_address", "LSM6DSOX adresse", 0, 127),
        ]
        for i, (key, label, mn, mx) in enumerate(i2c_fields):
            ig.addWidget(QLabel(label), i, 0)
            spin = QSpinBox()
            spin.setRange(mn, mx)
            spin.setFixedWidth(100)
            if "address" in key:
                spin.setPrefix("0x")
                spin.setDisplayIntegerBase(16)
            ig.addWidget(spin, i, 1)
            self._i2c_spins[key] = spin

        # Kontroll-sløyfe
        ig.addWidget(QLabel("Kontroll-rate (Hz)"), len(i2c_fields), 0)
        self._rate_spin = QDoubleSpinBox()
        self._rate_spin.setRange(10.0, 200.0)
        self._rate_spin.setSingleStep(5.0)
        self._rate_spin.setDecimals(0)
        self._rate_spin.setFixedWidth(100)
        ig.addWidget(self._rate_spin, len(i2c_fields), 1)

        upper.addWidget(i2c_box)
        root.addLayout(upper)

        # --- Servo-tabell ---
        servo_box = QGroupBox("Servokonfigurasjon (6 servoer)")
        stl = QVBoxLayout(servo_box)

        self._servo_table = QTableWidget(6, 8)
        self._servo_table.setHorizontalHeaderLabels([
            "Kanal", "Min puls (µs)", "Maks puls (µs)",
            "Min vinkel (°)", "Maks vinkel (°)", "Home (°)",
            "Retning", "Offset (°)",
        ])
        header = self._servo_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.Stretch)

        for i in range(6):
            self._servo_table.setVerticalHeaderItem(i, QTableWidgetItem(f"S{i + 1}"))

        stl.addWidget(self._servo_table)
        root.addWidget(servo_box, 1)

        # --- Knapperad ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._btn_validate = QPushButton("Valider")
        self._btn_validate.clicked.connect(self._on_validate)
        btn_row.addWidget(self._btn_validate)

        self._btn_apply = QPushButton("Bruk")
        self._btn_apply.clicked.connect(self._on_apply)
        btn_row.addWidget(self._btn_apply)

        self._btn_save = QPushButton("Lagre til fil")
        self._btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self._btn_save)

        self._btn_reload = QPushButton("Last inn på nytt")
        self._btn_reload.clicked.connect(self._on_reload)
        btn_row.addWidget(self._btn_reload)

        btn_row.addStretch()

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 11px;")
        btn_row.addWidget(self._status_label)

        root.addLayout(btn_row)

    def _load_config(self) -> None:
        """Last konfigurasjon fra bridge inn i UI."""
        cfg = self._bridge.config

        # Geometri
        self._geo_spins["base_radius"].setValue(cfg.base_radius)
        self._geo_spins["platform_radius"].setValue(cfg.platform_radius)
        self._geo_spins["servo_horn_length"].setValue(cfg.servo_horn_length)
        self._geo_spins["rod_length"].setValue(cfg.rod_length)
        self._geo_spins["home_height"].setValue(cfg.home_height)

        # I2C
        self._i2c_spins["i2c_bus_number"].setValue(cfg.i2c_bus_number)
        self._i2c_spins["pca9685_address"].setValue(cfg.pca9685_address)
        self._i2c_spins["pca9685_frequency"].setValue(cfg.pca9685_frequency)
        self._i2c_spins["lsm6dsox_address"].setValue(cfg.lsm6dsox_address)
        self._rate_spin.setValue(cfg.control_loop_rate_hz)

        # Servo-tabell
        for i, sc in enumerate(cfg.servo_configs[:6]):
            vals = [
                sc.channel, sc.min_pulse_us, sc.max_pulse_us,
                sc.min_angle_deg, sc.max_angle_deg, sc.home_angle_deg,
                sc.direction, sc.offset_deg,
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setTextAlignment(Qt.AlignCenter)
                self._servo_table.setItem(i, j, item)

    def _build_config_from_ui(self) -> PlatformConfig:
        """Bygg PlatformConfig fra UI-verdier."""
        cfg = PlatformConfig(
            base_radius=self._geo_spins["base_radius"].value(),
            platform_radius=self._geo_spins["platform_radius"].value(),
            servo_horn_length=self._geo_spins["servo_horn_length"].value(),
            rod_length=self._geo_spins["rod_length"].value(),
            home_height=self._geo_spins["home_height"].value(),
            i2c_bus_number=self._i2c_spins["i2c_bus_number"].value(),
            pca9685_address=self._i2c_spins["pca9685_address"].value(),
            pca9685_frequency=self._i2c_spins["pca9685_frequency"].value(),
            lsm6dsox_address=self._i2c_spins["lsm6dsox_address"].value(),
            control_loop_rate_hz=self._rate_spin.value(),
        )

        # Les servoer fra tabell
        servos = []
        for i in range(6):
            def cell(row: int, col: int) -> str:
                item = self._servo_table.item(row, col)
                return item.text() if item else "0"

            servos.append(ServoConfig(
                channel=int(cell(i, 0)),
                min_pulse_us=int(cell(i, 1)),
                max_pulse_us=int(cell(i, 2)),
                min_angle_deg=float(cell(i, 3)),
                max_angle_deg=float(cell(i, 4)),
                home_angle_deg=float(cell(i, 5)),
                direction=int(cell(i, 6)),
                offset_deg=float(cell(i, 7)),
            ))
        cfg.servo_configs = servos

        # Behold eksisterende PID og safety config
        old = self._bridge.config
        cfg.pid_gains = old.pid_gains
        cfg.safety_config = old.safety_config
        cfg.base_joint_angles = old.base_joint_angles
        cfg.platform_joint_angles = old.platform_joint_angles

        return cfg

    @Slot()
    def _on_validate(self) -> None:
        """Valider konfigurasjonen."""
        try:
            cfg = self._build_config_from_ui()
            errors = cfg.validate()
            if errors:
                self._status_label.setText(f"{len(errors)} feil funnet")
                self._status_label.setStyleSheet("font-size: 11px; color: #c53434;")
                QMessageBox.warning(self, "Valideringsfeil", "\n".join(errors))
            else:
                self._status_label.setText("Konfigurasjon gyldig")
                self._status_label.setStyleSheet("font-size: 11px; color: #4a9a3c;")
        except (ValueError, TypeError) as e:
            self._status_label.setText("Ugyldig input")
            self._status_label.setStyleSheet("font-size: 11px; color: #c53434;")
            QMessageBox.warning(self, "Ugyldig input", str(e))

    @Slot()
    def _on_apply(self) -> None:
        """Bruk konfigurasjonen."""
        try:
            cfg = self._build_config_from_ui()
            errors = self._bridge.update_config(cfg)
            if errors:
                self._status_label.setText(f"{len(errors)} feil")
                self._status_label.setStyleSheet("font-size: 11px; color: #c53434;")
                QMessageBox.warning(self, "Valideringsfeil", "\n".join(errors))
            else:
                self._status_label.setText("Konfigurasjon aktivert")
                self._status_label.setStyleSheet("font-size: 11px; color: #4a9a3c;")
        except (ValueError, TypeError) as e:
            self._status_label.setText("Feil ved aktivering")
            self._status_label.setStyleSheet("font-size: 11px; color: #c53434;")
            QMessageBox.warning(self, "Feil", str(e))

    @Slot()
    def _on_save(self) -> None:
        """Lagre konfigurasjon til fil."""
        ok = self._bridge.save_config()
        if ok:
            self._status_label.setText("Lagret til fil")
            self._status_label.setStyleSheet("font-size: 11px; color: #4a9a3c;")
        else:
            self._status_label.setText("Lagring feilet")
            self._status_label.setStyleSheet("font-size: 11px; color: #c53434;")

    @Slot()
    def _on_reload(self) -> None:
        """Last inn konfigurasjon fra bridge på nytt."""
        self._load_config()
        self._status_label.setText("Konfigurajon lastet inn")
        self._status_label.setStyleSheet("font-size: 11px; color: #666;")

    def update_from_snapshot(self, snapshot: StateSnapshot) -> None:
        """Config-tab trenger ikke hyppige snapshot-oppdateringer."""
        pass
