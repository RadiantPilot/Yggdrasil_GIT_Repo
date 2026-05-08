"""
config_tab.py · Tab 5: Konfigurasjon.

Redigerbar plattformkonfigurasjon: geometri, I2C-adresser,
servotabell, og valider/lagre-knapper.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
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

# Servo-tabelldefinisjon: (kolonne-indeks, label, widget-type, min, max, step, desimaler)
# direction er enten +1 eller -1 — bruk QSpinBox med step 2 og snap til oddetall.
_SERVO_COLS: list[tuple[str, str, float, float, float, int]] = [
    ("Kanal",         "int",   0,    15,    1,    0),
    ("Min puls (µs)", "int",   500,  2500,  10,   0),
    ("Maks puls (µs)","int",   500,  2500,  10,   0),
    ("Min vinkel (°)","float", -180, 180,   0.5,  1),
    ("Maks vinkel (°)","float",-180, 180,   0.5,  1),
    ("Home (°)",      "float", -180, 180,   0.5,  1),
    ("Retning",       "int",   -1,   1,     2,    0),
    ("Offset (°)",    "float", -90,  90,    0.5,  1),
]

_HIGHLIGHT = "background: #f9d77e;"
_ROW_FOCUS = "background: #e8f4f8;"

from ...config.platform_config import PlatformConfig, ServoConfig
from ..bridge.controller_bridge import ControllerBridge
from ..bridge.state_snapshot import StateSnapshot


class _NavigableGeoSpins(QWidget):
    """Geometriparametere (5 spinboxer) som navigerbar widget.

    nav_vertical sykler aktivt felt.
    nav_horizontal justerer aktivt felt med ett steg.
    """

    _FIELDS: list[tuple[str, str, float, float, float]] = [
        ("base_radius",       "Bunnradius (mm)",        10.0, 500.0, 1.0),
        ("platform_radius",   "Plattformradius (mm)",   10.0, 500.0, 1.0),
        ("servo_horn_length", "Servoarm (mm)",           5.0, 100.0, 0.5),
        ("rod_length",        "Staglengde (mm)",        50.0, 500.0, 1.0),
        ("home_height",       "Hvilehøyde (mm)",        20.0, 300.0, 1.0),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._active = 0
        self.spins: dict[str, QDoubleSpinBox] = {}
        self._labels: list[QLabel] = []

        lg = QGridLayout(self)
        lg.setSpacing(6)
        lg.setContentsMargins(0, 0, 0, 0)

        for i, (key, label, mn, mx, step) in enumerate(self._FIELDS):
            lbl = QLabel(label)
            lg.addWidget(lbl, i, 0)
            self._labels.append(lbl)

            spin = QDoubleSpinBox()
            spin.setRange(mn, mx)
            spin.setSingleStep(step)
            spin.setDecimals(1)
            spin.setFixedWidth(100)
            lg.addWidget(spin, i, 1)
            self.spins[key] = spin

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
        self._active = (self._active + delta) % len(self._FIELDS)
        self._highlight()

    def nav_horizontal(self, delta: int) -> None:
        key = self._FIELDS[self._active][0]
        spin = self.spins[key]
        spin.setValue(spin.value() + delta * spin.singleStep())

    def _highlight(self) -> None:
        for i, (key, *_) in enumerate(self._FIELDS):
            active = i == self._active
            self.spins[key].setStyleSheet(_HIGHLIGHT if active else "")
            self._labels[i].setStyleSheet("font-weight: 700;" if active else "")

    def _clear_highlight(self) -> None:
        for key in self.spins:
            self.spins[key].setStyleSheet("")
        for lbl in self._labels:
            lbl.setStyleSheet("")


class _NavigableI2CSpins(QWidget):
    """I2C-innstillinger + kontrollrate (5 felter) som navigerbar widget.

    nav_vertical sykler aktivt felt.
    nav_horizontal justerer aktivt felt med ett steg.
    """

    _I2C_FIELDS: list[tuple[str, str, int, int]] = [
        ("i2c_bus_number",   "Buss-nummer",       0,    10),
        ("pca9685_address",  "PCA9685 adresse",   0,   127),
        ("pca9685_frequency","PWM frekvens (Hz)", 24,  1526),
        ("lsm6dsox_address", "LSM6DSOX adresse",  0,   127),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._active = 0
        self._n_fields = len(self._I2C_FIELDS) + 1  # +1 for rate
        self.spins: dict[str, QSpinBox] = {}
        self._labels: list[QLabel] = []
        self._all_spins: list[QSpinBox | QDoubleSpinBox] = []

        lg = QGridLayout(self)
        lg.setSpacing(6)
        lg.setContentsMargins(0, 0, 0, 0)

        for i, (key, label, mn, mx) in enumerate(self._I2C_FIELDS):
            lbl = QLabel(label)
            lg.addWidget(lbl, i, 0)
            self._labels.append(lbl)

            spin = QSpinBox()
            spin.setRange(mn, mx)
            spin.setFixedWidth(100)
            if "address" in key:
                spin.setPrefix("0x")
                spin.setDisplayIntegerBase(16)
            lg.addWidget(spin, i, 1)
            self.spins[key] = spin
            self._all_spins.append(spin)

        # Kontrollrate som siste felt
        rate_lbl = QLabel("Kontroll-rate (Hz)")
        lg.addWidget(rate_lbl, len(self._I2C_FIELDS), 0)
        self._labels.append(rate_lbl)

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(10.0, 200.0)
        self.rate_spin.setSingleStep(5.0)
        self.rate_spin.setDecimals(0)
        self.rate_spin.setFixedWidth(100)
        lg.addWidget(self.rate_spin, len(self._I2C_FIELDS), 1)
        self._all_spins.append(self.rate_spin)

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
        self._active = (self._active + delta) % self._n_fields
        self._highlight()

    def nav_horizontal(self, delta: int) -> None:
        spin = self._all_spins[self._active]
        spin.setValue(spin.value() + delta * spin.singleStep())

    def _highlight(self) -> None:
        for i, spin in enumerate(self._all_spins):
            active = i == self._active
            spin.setStyleSheet(_HIGHLIGHT if active else "")
            self._labels[i].setStyleSheet("font-weight: 700;" if active else "")

    def _clear_highlight(self) -> None:
        for spin in self._all_spins:
            spin.setStyleSheet("")
        for lbl in self._labels:
            lbl.setStyleSheet("")


class _NavigableServoTable(QWidget):
    """Servokonfigurasjonstabell (6 × 8 spinboxer) som navigerbar widget.

    To-nivå-navigasjon:
    - NAV-MODE  (fokusert):  nav_vertical bytter aktiv rad, hele raden utheves.
    - EDIT-MODE (etter enter): nav_vertical sykler kolonne, nav_horizontal justerer verdi.
    """

    def __init__(self) -> None:
        super().__init__()
        self._active_row = 0
        self._active_col = 0
        self._in_edit = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        col_labels = [c[0] for c in _SERVO_COLS]
        self.table = QTableWidget(6, len(_SERVO_COLS))
        self.table.setHorizontalHeaderLabels(col_labels)
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.Stretch)

        for i in range(6):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(f"S{i + 1}"))

        for row in range(6):
            for col, (_, wtype, mn, mx, step, decimals) in enumerate(_SERVO_COLS):
                if wtype == "int":
                    spin: QSpinBox | QDoubleSpinBox = QSpinBox()
                    spin.setRange(int(mn), int(mx))
                    spin.setSingleStep(int(step))
                else:
                    spin = QDoubleSpinBox()
                    spin.setRange(mn, mx)
                    spin.setSingleStep(step)
                    spin.setDecimals(decimals)
                spin.setFrame(False)
                self.table.setCellWidget(row, col, spin)

        layout.addWidget(self.table)

    def set_focused(self, focused: bool) -> None:
        if focused:
            self._highlight()
        else:
            self._clear_highlight()

    def set_edit_mode(self, edit: bool) -> None:
        self._in_edit = edit
        if edit:
            self._highlight()
        else:
            self._active_col = 0
            # Highlight-tilstand styres av set_focused() — ikke rør den her

    def nav_vertical(self, delta: int) -> None:
        if self._in_edit:
            self._active_col = (self._active_col + delta) % len(_SERVO_COLS)
        else:
            self._active_row = (self._active_row + delta) % 6
        self._highlight()

    def nav_horizontal(self, delta: int) -> None:
        if self._in_edit:
            spin = self.table.cellWidget(self._active_row, self._active_col)
            if spin is not None:
                spin.setValue(spin.value() + delta * spin.singleStep())

    def _highlight(self) -> None:
        for row in range(6):
            for col in range(len(_SERVO_COLS)):
                spin = self.table.cellWidget(row, col)
                if spin is None:
                    continue
                if row == self._active_row:
                    if self._in_edit and col == self._active_col:
                        spin.setStyleSheet(_HIGHLIGHT)
                    else:
                        spin.setStyleSheet(_ROW_FOCUS)
                else:
                    spin.setStyleSheet("")

    def _clear_highlight(self) -> None:
        for row in range(6):
            for col in range(len(_SERVO_COLS)):
                spin = self.table.cellWidget(row, col)
                if spin is not None:
                    spin.setStyleSheet("")


class _NavigableActionButtons(QWidget):
    """Handlingsknapper (Valider / Bruk / Lagre / Last inn) som navigerbar widget.

    nav_vertical sykler aktiv knapp.
    nav_horizontal utløser aktiv knapp.
    """

    validate_requested = Signal()
    apply_requested = Signal()
    save_requested = Signal()
    reload_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._active = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._btn_validate = QPushButton("Valider")
        self._btn_validate.clicked.connect(self.validate_requested)
        layout.addWidget(self._btn_validate)

        self.btn_apply = QPushButton("Bruk")
        self.btn_apply.setToolTip(
            "Aktiverer ny konfigurasjon ved full reinit av domenet.\n"
            "Krever at kontrollsløyfen er stoppet."
        )
        self.btn_apply.clicked.connect(self.apply_requested)
        layout.addWidget(self.btn_apply)

        self._btn_save = QPushButton("Lagre til fil")
        self._btn_save.clicked.connect(self.save_requested)
        layout.addWidget(self._btn_save)

        self._btn_reload = QPushButton("Last inn på nytt")
        self._btn_reload.clicked.connect(self.reload_requested)
        layout.addWidget(self._btn_reload)

        layout.addStretch()

        self._buttons = [
            self._btn_validate,
            self.btn_apply,
            self._btn_save,
            self._btn_reload,
        ]

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
        self._active = (self._active + delta) % len(self._buttons)
        self._highlight()

    def nav_horizontal(self, delta: int) -> None:
        self._buttons[self._active].click()

    def _highlight(self) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setStyleSheet(_HIGHLIGHT if i == self._active else "")

    def _clear_highlight(self) -> None:
        for btn in self._buttons:
            btn.setStyleSheet("")


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
        geo_layout = QVBoxLayout(geo_box)
        geo_layout.setContentsMargins(8, 8, 8, 8)
        self._geo_widget = _NavigableGeoSpins()
        self._geo_spins = self._geo_widget.spins
        geo_layout.addWidget(self._geo_widget)
        upper.addWidget(geo_box)

        # I2C-innstillinger
        i2c_box = QGroupBox("I2C-innstillinger")
        i2c_layout = QVBoxLayout(i2c_box)
        i2c_layout.setContentsMargins(8, 8, 8, 8)
        self._i2c_widget = _NavigableI2CSpins()
        self._i2c_spins = self._i2c_widget.spins
        self._rate_spin = self._i2c_widget.rate_spin
        i2c_layout.addWidget(self._i2c_widget)
        upper.addWidget(i2c_box)

        root.addLayout(upper)

        # --- Servo-tabell ---
        servo_box = QGroupBox("Servokonfigurasjon (6 servoer)")
        stl = QVBoxLayout(servo_box)
        self._servo_widget = _NavigableServoTable()
        self._servo_table = self._servo_widget.table
        stl.addWidget(self._servo_widget)
        root.addWidget(servo_box, 1)

        # --- Knapperad ---
        btn_box = QGroupBox()
        btn_box.setFlat(True)
        btn_layout = QVBoxLayout(btn_box)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self._action_widget = _NavigableActionButtons()
        self._btn_validate = self._action_widget._btn_validate
        self._btn_apply = self._action_widget.btn_apply
        self._btn_save = self._action_widget._btn_save
        self._btn_reload = self._action_widget._btn_reload

        self._action_widget.validate_requested.connect(self._on_validate)
        self._action_widget.apply_requested.connect(self._on_apply)
        self._action_widget.save_requested.connect(self._on_save)
        self._action_widget.reload_requested.connect(self._on_reload)

        btn_layout.addWidget(self._action_widget)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 11px;")
        btn_layout.addWidget(self._status_label)

        root.addWidget(btn_box)

    def get_navigables(self) -> list:
        """Returnerer navigerbare widgets i visuell rekkefølge (topp→bunn)."""
        return [
            self._geo_widget,
            self._i2c_widget,
            self._servo_widget,
            self._action_widget,
        ]

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
                widget = self._servo_table.cellWidget(i, j)
                if widget is not None:
                    widget.setValue(v)

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

        # Les servoer fra tabell via spinbox-widgets
        servos = []
        for i in range(6):
            def cell_val(row: int, col: int) -> float:
                widget = self._servo_table.cellWidget(row, col)
                return widget.value() if widget is not None else 0.0

            servos.append(ServoConfig(
                channel=int(cell_val(i, 0)),
                min_pulse_us=int(cell_val(i, 1)),
                max_pulse_us=int(cell_val(i, 2)),
                min_angle_deg=float(cell_val(i, 3)),
                max_angle_deg=float(cell_val(i, 4)),
                home_angle_deg=float(cell_val(i, 5)),
                direction=int(cell_val(i, 6)),
                offset_deg=float(cell_val(i, 7)),
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
        """Bruk konfigurasjonen (full reinit av domenet)."""
        try:
            cfg = self._build_config_from_ui()
            errors = self._bridge.update_config(cfg)
            if errors:
                self._status_label.setText(f"{len(errors)} feil")
                self._status_label.setStyleSheet("font-size: 11px; color: #c53434;")
                QMessageBox.warning(self, "Kan ikke aktivere", "\n".join(errors))
            else:
                # Re-les fra bridge slik at UI-et reflekterer den faktiske
                # aktive configen (normalisert av PlatformConfig.__post_init__).
                self._load_config()
                self._status_label.setText("Konfigurasjon aktivert · domenet reinitialisert")
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
        """Disable Bruk-knappen mens kontrollsløyfen kjører.

        Strukturelle config-endringer krever full reinit av domenet, så
        sløyfen må være stoppet først. Andre felt holdes redigerbare slik
        at brukeren kan forberede endringer mens systemet kjører.
        """
        running = snapshot.is_running
        self._btn_apply.setEnabled(not running)
        if running:
            self._status_label.setText("Stopp sløyfen for å aktivere endringer")
            self._status_label.setStyleSheet("font-size: 11px; color: #888;")
