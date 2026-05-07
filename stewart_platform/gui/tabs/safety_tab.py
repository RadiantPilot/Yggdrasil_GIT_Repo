"""
safety_tab.py · Tab 6: Sikkerhet.

E-STOP-banner, sikkerhetssjekk-indikatorer, grense-editering,
watchdog-status og hendelseslogg.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...config.platform_config import SafetyConfig
from ...safety.safety_monitor import SafetySeverity
from ..bridge.controller_bridge import ControllerBridge
from ..bridge.state_snapshot import StateSnapshot
from ..widgets.event_log import EventLog
from ..widgets.indicator_lamp import IndicatorLamp


_ESTOP_BASE = (
    "QPushButton { background: #c0392b; color: white; font-weight: bold; "
    "font-size: 14px; border-radius: 6px; border: 2px solid transparent; }"
    "QPushButton:hover { background: #a93226; }"
)
_ESTOP_ACTIVE = (
    "QPushButton { background: #c0392b; color: white; font-weight: bold; "
    "font-size: 14px; border-radius: 6px; border: 2px solid #f39c12; }"
    "QPushButton:hover { background: #a93226; }"
)


class _NavigableEstopButtons(QWidget):
    """E-STOP + Tilbakestill som navigerbar widget for knappekortet.

    nav_vertical sykler mellom de to knappene.
    nav_horizontal utløser den aktive knappen.
    """

    estop_requested = Signal()
    reset_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._active = 0  # 0=E-STOP, 1=Tilbakestill
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._btn_estop = QPushButton("E-STOP")
        self._btn_estop.setFixedSize(120, 50)
        self._btn_estop.setStyleSheet(_ESTOP_BASE)
        self._btn_estop.clicked.connect(self.estop_requested)
        layout.addWidget(self._btn_estop)

        self._btn_reset = QPushButton("Tilbakestill")
        self._btn_reset.setFixedSize(120, 30)
        self._btn_reset.clicked.connect(self.reset_requested)
        layout.addWidget(self._btn_reset)

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
        self._active = (self._active + delta) % 2
        self._highlight()

    def nav_horizontal(self, delta: int) -> None:
        if self._active == 0:
            self.estop_requested.emit()
        else:
            self.reset_requested.emit()

    def _highlight(self) -> None:
        self._btn_estop.setStyleSheet(_ESTOP_ACTIVE if self._active == 0 else _ESTOP_BASE)
        self._btn_reset.setStyleSheet("background: #f9d77e;" if self._active == 1 else "")

    def _clear_highlight(self) -> None:
        self._btn_estop.setStyleSheet(_ESTOP_BASE)
        self._btn_reset.setStyleSheet("")


class _NavigableLimitsEditor(QWidget):
    """Sikkerhetsgrenser (4 spins + Bruk-knapp) som navigerbar widget.

    nav_vertical sykler mellom de 4 feltene og Bruk-knappen.
    nav_horizontal justerer aktiv spinbox med ett steg, eller trykker Bruk.
    """

    apply_requested = Signal()

    _FIELDS: list[tuple[str, str, float, float, float]] = [
        ("max_rotation_deg",             "Maks rotasjon (°)",          1.0,  90.0, 1.0),
        ("max_angular_velocity_deg_per_s","Maks vinkelhastighet (°/s)", 1.0, 360.0, 5.0),
        ("servo_angle_margin_deg",        "Servomargin (°)",            0.0,  30.0, 0.5),
        ("imu_fault_threshold_g",         "IMU-terskel (g)",            0.5,  20.0, 0.5),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._active = 0
        self._n_spins = len(self._FIELDS)

        lg = QGridLayout(self)
        lg.setSpacing(6)
        lg.setContentsMargins(0, 0, 0, 0)

        self.spins: dict[str, QDoubleSpinBox] = {}
        self._labels: list[QLabel] = []

        for i, (key, label, mn, mx, step) in enumerate(self._FIELDS):
            lbl = QLabel(label)
            lg.addWidget(lbl, i, 0)
            self._labels.append(lbl)

            spin = QDoubleSpinBox()
            spin.setRange(mn, mx)
            spin.setSingleStep(step)
            spin.setDecimals(1)
            spin.setFixedWidth(90)
            lg.addWidget(spin, i, 1)
            self.spins[key] = spin

        btn_row = QHBoxLayout()
        self._btn_apply = QPushButton("Bruk grenser")
        self._btn_apply.clicked.connect(self.apply_requested)
        btn_row.addWidget(self._btn_apply)
        btn_row.addStretch()
        lg.addLayout(btn_row, self._n_spins, 0, 1, 2)

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
        self._active = (self._active + delta) % (self._n_spins + 1)
        self._highlight()

    def nav_horizontal(self, delta: int) -> None:
        if self._active < self._n_spins:
            key = self._FIELDS[self._active][0]
            spin = self.spins[key]
            spin.setValue(spin.value() + delta * spin.singleStep())
        else:
            self.apply_requested.emit()

    def _highlight(self) -> None:
        for i, (key, *_) in enumerate(self._FIELDS):
            active = i == self._active
            self.spins[key].setStyleSheet("background: #f9d77e;" if active else "")
            self._labels[i].setStyleSheet("font-weight: 700;" if active else "")
        self._btn_apply.setStyleSheet(
            "background: #f9d77e;" if self._active == self._n_spins else ""
        )

    def _clear_highlight(self) -> None:
        for key in self.spins:
            self.spins[key].setStyleSheet("")
        for lbl in self._labels:
            lbl.setStyleSheet("")
        self._btn_apply.setStyleSheet("")


class SafetyTab(QWidget):
    """Sikkerhetsfane med E-STOP, sjekker, grenser og hendelseslogg."""

    def __init__(self, bridge: ControllerBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._last_event_ts: float = 0.0
        self._build_ui()
        self._load_limits()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # --- E-STOP banner + knapper ---
        estop_row = QHBoxLayout()
        estop_row.setSpacing(16)

        self._estop_banner = QLabel("SYSTEM OK")
        self._estop_banner.setAlignment(Qt.AlignCenter)
        self._estop_banner.setMinimumHeight(60)
        self._estop_banner.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #4a9a3c; "
            "background: rgba(74,154,60,0.10); border: 2px solid rgba(74,154,60,0.3); "
            "border-radius: 6px; padding: 8px;"
        )
        estop_row.addWidget(self._estop_banner, 1)

        self._estop_panel = _NavigableEstopButtons()
        self._estop_panel.estop_requested.connect(self._on_estop)
        self._estop_panel.reset_requested.connect(self._on_reset)
        estop_row.addWidget(self._estop_panel)

        root.addLayout(estop_row)

        # --- Midtre rad: sjekker + grenser ---
        mid = QHBoxLayout()
        mid.setSpacing(12)

        checks_box = QGroupBox("Sikkerhetssjekker")
        cl = QVBoxLayout(checks_box)
        cl.setSpacing(6)

        self._check_lamps: dict[str, IndicatorLamp] = {}
        check_names = [
            ("pose_ok",     "Rotasjon innenfor grenser"),
            ("servo_ok",    "Servovinkler gyldige"),
            ("velocity_ok", "Vinkelhastighet innenfor grenser"),
            ("imu_ok",      "IMU-data gyldig"),
            ("watchdog_ok", "Watchdog aktiv"),
            ("estop_clear", "E-STOP ikke utløst"),
        ]
        for key, label in check_names:
            lamp = IndicatorLamp(label, on=True, color="green")
            cl.addWidget(lamp)
            self._check_lamps[key] = lamp

        cl.addStretch()

        self._last_check_label = QLabel("Ingen sjekker utført")
        self._last_check_label.setStyleSheet("font-size: 10px; color: #888;")
        cl.addWidget(self._last_check_label)

        mid.addWidget(checks_box, 1)

        limits_box = QGroupBox("Sikkerhetsgrenser")
        ll = QVBoxLayout(limits_box)
        ll.setContentsMargins(8, 8, 8, 8)

        self._limits_editor = _NavigableLimitsEditor()
        self._limits_editor.apply_requested.connect(self._on_apply_limits)
        ll.addWidget(self._limits_editor)

        # Bakoverkompatibilitet: _load_limits og _on_apply_limits bruker dette
        self._limit_spins = self._limits_editor.spins

        mid.addWidget(limits_box, 1)
        root.addLayout(mid)

        # --- Hendelseslogg ---
        log_box = QGroupBox("Sikkerhetshendelser")
        ll2 = QVBoxLayout(log_box)
        self._event_log = EventLog(max_events=30)
        ll2.addWidget(self._event_log)
        root.addWidget(log_box, 1)

    def get_navigables(self) -> list:
        """E-STOP-panel + grenseeditor for FocusManager."""
        return [self._estop_panel, self._limits_editor]

    def _load_limits(self) -> None:
        cfg = self._bridge.config.safety_config
        self._limit_spins["max_rotation_deg"].setValue(cfg.max_rotation_deg)
        self._limit_spins["max_angular_velocity_deg_per_s"].setValue(cfg.max_angular_velocity_deg_per_s)
        self._limit_spins["servo_angle_margin_deg"].setValue(cfg.servo_angle_margin_deg)
        self._limit_spins["imu_fault_threshold_g"].setValue(cfg.imu_fault_threshold_g)

    @Slot()
    def _on_estop(self) -> None:
        self._bridge.trigger_e_stop("Manuell E-STOP fra sikkerhetspanel")

    @Slot()
    def _on_reset(self) -> None:
        ok = self._bridge.reset_latched_faults()
        if not ok:
            self._event_log.add_event("WARN", "Ingen feil å tilbakestille")

    @Slot()
    def _on_apply_limits(self) -> None:
        cfg = self._bridge.config.safety_config
        new_config = SafetyConfig(
            max_rotation_deg=self._limit_spins["max_rotation_deg"].value(),
            max_angular_velocity_deg_per_s=self._limit_spins["max_angular_velocity_deg_per_s"].value(),
            servo_angle_margin_deg=self._limit_spins["servo_angle_margin_deg"].value(),
            watchdog_timeout_s=cfg.watchdog_timeout_s,
            imu_fault_threshold_g=self._limit_spins["imu_fault_threshold_g"].value(),
        )
        self._bridge.update_safety_limits(new_config)
        self._event_log.add_event("INFO", "Sikkerhetsgrenser oppdatert")

    def update_from_snapshot(self, snapshot: StateSnapshot) -> None:
        """Oppdater sikkerhetsvisning fra snapshot."""
        if snapshot.is_e_stopped:
            reason = snapshot.e_stop_reason or "Ukjent årsak"
            self._estop_banner.setText(f"NØDSTOPP AKTIV — {reason}")
            self._estop_banner.setStyleSheet(
                "font-size: 20px; font-weight: bold; color: #c53434; "
                "background: rgba(197,52,52,0.15); border: 2px solid rgba(197,52,52,0.5); "
                "border-radius: 6px; padding: 8px;"
            )
        elif snapshot.is_running:
            self._estop_banner.setText("SYSTEM KJØRER — OK")
            self._estop_banner.setStyleSheet(
                "font-size: 20px; font-weight: bold; color: #4a9a3c; "
                "background: rgba(74,154,60,0.10); border: 2px solid rgba(74,154,60,0.3); "
                "border-radius: 6px; padding: 8px;"
            )
        else:
            self._estop_banner.setText("SYSTEM STOPPET")
            self._estop_banner.setStyleSheet(
                "font-size: 20px; font-weight: bold; color: #888; "
                "background: rgba(160,160,160,0.08); border: 2px solid rgba(160,160,160,0.3); "
                "border-radius: 6px; padding: 8px;"
            )

        result = snapshot.latest_safety_result
        if result is not None:
            joined = " ".join(result.violations)

            def has(keyword: str) -> bool:
                return keyword.lower() in joined.lower()

            self._check_lamps["pose_ok"].set_state(
                not has("Rotasjon utenfor"),
                "green" if not has("Rotasjon utenfor") else "red",
            )
            self._check_lamps["servo_ok"].set_state(
                not has("Servovinkler utenfor"),
                "green" if not has("Servovinkler utenfor") else "red",
            )
            self._check_lamps["velocity_ok"].set_state(
                not has("Vinkelhastighet"),
                "green" if not has("Vinkelhastighet") else "red",
            )
            self._check_lamps["imu_ok"].set_state(
                not has("IMU-akselerasjon"),
                "green" if not has("IMU-akselerasjon") else "red",
            )

            n_checks = len(snapshot.safety_results)
            n_fail = sum(1 for r in snapshot.safety_results if not r.is_safe)
            self._last_check_label.setText(f"Siste {n_checks} sjekker — {n_fail} brudd")

        self._check_lamps["estop_clear"].set_state(
            not snapshot.is_e_stopped,
            "green" if not snapshot.is_e_stopped else "red",
        )
        self._check_lamps["watchdog_ok"].set_state(
            snapshot.is_running or not snapshot.is_e_stopped,
            "green" if (snapshot.is_running or not snapshot.is_e_stopped) else "yellow",
        )

        events = self._bridge.get_events()
        new_events = [ev for ev in events if ev.timestamp > self._last_event_ts]
        if new_events:
            self._last_event_ts = new_events[0].timestamp
            for ev in reversed(new_events):
                self._event_log.add_event(ev.level, ev.message)
