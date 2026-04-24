"""
safety_tab.py · Tab 6: Sikkerhet.

E-STOP-banner, sikkerhetssjekk-indikatorer, grense-editering,
watchdog-status og hendelseslogg.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
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


class SafetyTab(QWidget):
    """Sikkerhetsfane med E-STOP, sjekker, grenser og hendelseslogg."""

    def __init__(self, bridge: ControllerBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._build_ui()
        self._load_limits()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # --- E-STOP banner ---
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

        btn_col = QVBoxLayout()
        self._btn_estop = QPushButton("E-STOP")
        self._btn_estop.setFixedSize(120, 50)
        self._btn_estop.setStyleSheet(
            "QPushButton { background: #c0392b; color: white; "
            "font-weight: bold; font-size: 14px; border-radius: 6px; }"
            "QPushButton:hover { background: #a93226; }"
        )
        self._btn_estop.clicked.connect(self._on_estop)
        btn_col.addWidget(self._btn_estop)

        self._btn_reset = QPushButton("Tilbakestill")
        self._btn_reset.setFixedSize(120, 30)
        self._btn_reset.clicked.connect(self._on_reset)
        btn_col.addWidget(self._btn_reset)

        estop_row.addLayout(btn_col)
        root.addLayout(estop_row)

        # --- Midtre rad: sjekker + grenser ---
        mid = QHBoxLayout()
        mid.setSpacing(12)

        # Sikkerhetssjekker
        checks_box = QGroupBox("Sikkerhetssjekker")
        cl = QVBoxLayout(checks_box)
        cl.setSpacing(6)

        self._check_lamps: dict[str, IndicatorLamp] = {}
        check_names = [
            ("pose_ok", "Pose innenfor grenser"),
            ("servo_ok", "Servovinkler gyldige"),
            ("velocity_ok", "Hastighet innenfor grenser"),
            ("imu_ok", "IMU-data gyldig"),
            ("watchdog_ok", "Watchdog aktiv"),
            ("estop_clear", "E-STOP ikke utløst"),
        ]
        for key, label in check_names:
            lamp = IndicatorLamp(label, on=True, color="green")
            cl.addWidget(lamp)
            self._check_lamps[key] = lamp

        cl.addStretch()

        # Siste sjekk-resultat
        self._last_check_label = QLabel("Ingen sjekker utført")
        self._last_check_label.setStyleSheet("font-size: 10px; color: #888;")
        cl.addWidget(self._last_check_label)

        mid.addWidget(checks_box, 1)

        # Sikkerhetsgrenser
        limits_box = QGroupBox("Sikkerhetsgrenser")
        lg = QGridLayout(limits_box)
        lg.setSpacing(6)

        self._limit_spins: dict[str, QDoubleSpinBox] = {}
        limit_fields = [
            ("max_translation_mm", "Maks translasjon (mm)", 1.0, 200.0, 1.0),
            ("max_rotation_deg", "Maks rotasjon (°)", 1.0, 90.0, 1.0),
            ("max_velocity_mm_per_s", "Maks hastighet (mm/s)", 1.0, 500.0, 5.0),
            ("max_angular_velocity_deg_per_s", "Maks vinkelhastighet (°/s)", 1.0, 360.0, 5.0),
            ("servo_angle_margin_deg", "Servomargin (°)", 0.0, 30.0, 0.5),
            ("watchdog_timeout_s", "Watchdog timeout (s)", 0.1, 10.0, 0.1),
            ("imu_fault_threshold_g", "IMU-terskel (g)", 0.5, 20.0, 0.5),
        ]
        for i, (key, label, mn, mx, step) in enumerate(limit_fields):
            lg.addWidget(QLabel(label), i, 0)
            spin = QDoubleSpinBox()
            spin.setRange(mn, mx)
            spin.setSingleStep(step)
            spin.setDecimals(1)
            spin.setFixedWidth(90)
            lg.addWidget(spin, i, 1)
            self._limit_spins[key] = spin

        # Knapper for grenser
        lim_btn_row = QHBoxLayout()
        self._btn_apply_limits = QPushButton("Bruk grenser")
        self._btn_apply_limits.clicked.connect(self._on_apply_limits)
        lim_btn_row.addWidget(self._btn_apply_limits)
        lim_btn_row.addStretch()
        lg.addLayout(lim_btn_row, len(limit_fields), 0, 1, 2)

        mid.addWidget(limits_box, 1)

        root.addLayout(mid)

        # --- Hendelseslogg ---
        log_box = QGroupBox("Sikkerhetshendelser")
        ll = QVBoxLayout(log_box)
        self._event_log = EventLog(max_events=30)
        ll.addWidget(self._event_log)
        root.addWidget(log_box, 1)

    def _load_limits(self) -> None:
        """Last sikkerhetsgrenser fra config."""
        cfg = self._bridge.config.safety_config
        self._limit_spins["max_translation_mm"].setValue(cfg.max_translation_mm)
        self._limit_spins["max_rotation_deg"].setValue(cfg.max_rotation_deg)
        self._limit_spins["max_velocity_mm_per_s"].setValue(cfg.max_velocity_mm_per_s)
        self._limit_spins["max_angular_velocity_deg_per_s"].setValue(cfg.max_angular_velocity_deg_per_s)
        self._limit_spins["servo_angle_margin_deg"].setValue(cfg.servo_angle_margin_deg)
        self._limit_spins["watchdog_timeout_s"].setValue(cfg.watchdog_timeout_s)
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
        """Bruk nye sikkerhetsgrenser."""
        new_config = SafetyConfig(
            max_translation_mm=self._limit_spins["max_translation_mm"].value(),
            max_rotation_deg=self._limit_spins["max_rotation_deg"].value(),
            max_velocity_mm_per_s=self._limit_spins["max_velocity_mm_per_s"].value(),
            max_angular_velocity_deg_per_s=self._limit_spins["max_angular_velocity_deg_per_s"].value(),
            servo_angle_margin_deg=self._limit_spins["servo_angle_margin_deg"].value(),
            watchdog_timeout_s=self._limit_spins["watchdog_timeout_s"].value(),
            imu_fault_threshold_g=self._limit_spins["imu_fault_threshold_g"].value(),
        )
        self._bridge.update_safety_limits(new_config)
        self._event_log.add_event("INFO", "Sikkerhetsgrenser oppdatert")

    def update_from_snapshot(self, snapshot: StateSnapshot) -> None:
        """Oppdater sikkerhetsvisning fra snapshot."""
        # E-STOP banner
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

        # Sikkerhetssjekker — basert på siste resultat
        result = snapshot.latest_safety_result
        if result is not None:
            violations = set(result.violations)
            self._check_lamps["pose_ok"].set_state(
                "Pose utenfor tillatte grenser." not in violations,
                "green" if "Pose utenfor tillatte grenser." not in violations else "red",
            )
            self._check_lamps["servo_ok"].set_state(
                "Servovinkler utenfor tillatte grenser." not in violations,
                "green" if "Servovinkler utenfor tillatte grenser." not in violations else "red",
            )
            self._check_lamps["velocity_ok"].set_state(
                "Hastighet over tillatt grense." not in violations,
                "green" if "Hastighet over tillatt grense." not in violations else "red",
            )
            self._check_lamps["imu_ok"].set_state(
                "IMU-akselerasjon over feilterskel." not in violations,
                "green" if "IMU-akselerasjon over feilterskel." not in violations else "red",
            )

            n_checks = len(snapshot.safety_results)
            n_fail = sum(1 for r in snapshot.safety_results if not r.is_safe)
            self._last_check_label.setText(
                f"Siste {n_checks} sjekker — {n_fail} brudd"
            )

        # E-stop og watchdog lamper
        self._check_lamps["estop_clear"].set_state(
            not snapshot.is_e_stopped,
            "green" if not snapshot.is_e_stopped else "red",
        )
        self._check_lamps["watchdog_ok"].set_state(
            snapshot.is_running or not snapshot.is_e_stopped,
            "green" if (snapshot.is_running or not snapshot.is_e_stopped) else "yellow",
        )

        # Hendelseslogg — synkroniser fra bridge
        events = self._bridge.get_events()
        current_count = len(self._event_log._events)
        if len(events) > current_count:
            for ev in reversed(events[current_count:]):
                self._event_log.add_event(ev.level, ev.message)
