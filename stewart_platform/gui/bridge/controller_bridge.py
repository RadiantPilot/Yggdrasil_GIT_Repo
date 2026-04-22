"""
controller_bridge.py · Eneste tilkoblingspunkt mellom GUI og domene.

Holder referanser til MotionController (og dens underkomponenter)
og oversetter GUI-kall til domene-operasjoner. Tilbyr både ekte
hardware-modus og `mock=True` for utvikling uten Raspberry Pi.

GUI-widgets skal **aldri** importere fra control/, safety/ eller
hardware/ direkte. Alt går gjennom denne klassen.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from ...config.platform_config import Axis, PIDGains, PlatformConfig, SafetyConfig
from ...control.motion_controller import MotionController
from ...geometry.pose import Pose
from ...geometry.vector3 import Vector3
from ...safety.safety_monitor import SafetyCheckResult
from .state_snapshot import StateSnapshot


@dataclass
class BridgeEvent:
    """Én hendelse logget av bridge."""
    timestamp: float
    level: str   # "INFO", "WARN", "FAIL"
    message: str


class CalibrationResult(Enum):
    """Resultat av et kalibreringsforsøk.

    OK          — kalibrering fullført (hardware eller mock).
    NOT_READY   — ingen IMU tilgjengelig (ikke initialisert).
    NOT_IMPL    — driveren har ikke implementert kalibreringen enda.
    FAILED      — kalibrering startet men feilet underveis.
    """
    OK = "ok"
    NOT_READY = "not_ready"
    NOT_IMPL = "not_impl"
    FAILED = "failed"


class ControllerBridge(QObject):
    """Adapter mellom GUI og stewart_platform-domenet.

    I mock-modus instansieres ingen hardware — alle avlesninger
    simuleres (tilfeldige/sinusformede verdier) og alle settere
    lagres bare internt. Dette lar GUI-et utvikles og testes uten
    Pi, servoer eller IMU.
    """

    # Qt-signaler som GUI-widgets kan koble seg på
    target_pose_changed = Signal(object)       # emit Pose
    pid_gains_changed = Signal(object, object)  # emit (Axis, PIDGains)
    safety_fault = Signal(object)              # emit SafetyCheckResult
    config_changed = Signal(object)            # emit PlatformConfig

    def __init__(
        self,
        config_path: Path,
        mock: bool = False,
    ) -> None:
        """Opprett bridge.

        Args:
            config_path: Sti til YAML-config (brukes for både ekte og mock).
            mock: Hvis True, kjør uten hardware.
        """
        super().__init__()
        self._config_path = config_path
        self._mock = mock
        self._controller: Optional[MotionController] = None
        self._config: Optional[PlatformConfig] = None
        self._started_at = time.monotonic()
        self._last_snapshot_time = self._started_at

        # Hendelseslogg — brukes av overview og safety tabs
        self._events: deque[BridgeEvent] = deque(maxlen=100)

        # Mock-tilstand — kun brukt når self._mock er True
        self._mock_running = False
        self._mock_e_stopped = False
        self._mock_e_stop_reason: Optional[str] = None
        self._mock_target_pose = Pose.home()
        self._mock_pid_gains: dict[Axis, PIDGains] = {}
        self._mock_safety_results: deque[SafetyCheckResult] = deque(maxlen=50)

    # ------------------------------------------------------------------
    # Livssyklus
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Last config og initialiser domene (med mindre mock)."""
        if self._config_path.exists():
            self._config = PlatformConfig.load(str(self._config_path))
        else:
            # Ingen config-fil — bruk default (vanlig i mock-kjøring)
            self._config = PlatformConfig()

        if self._mock:
            # Initialiser mock-PID-gains fra config
            for axis in Axis:
                self._mock_pid_gains[axis] = PIDGains(
                    kp=self._config.pid_gains.kp,
                    ki=self._config.pid_gains.ki,
                    kd=self._config.pid_gains.kd,
                    output_min=self._config.pid_gains.output_min,
                    output_max=self._config.pid_gains.output_max,
                    integral_limit=self._config.pid_gains.integral_limit,
                )
            return

        # Ekte hardware-modus
        self._controller = MotionController(self._config)
        self._controller.initialize()

    def shutdown(self) -> None:
        """Rydde avslutning — stopp loop, frikoble servoer."""
        if self._controller is not None:
            self._controller.shutdown()
            self._controller = None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_mock(self) -> bool:
        return self._mock

    @property
    def config(self) -> PlatformConfig:
        assert self._config is not None, "initialize() må kalles først"
        return self._config

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def get_snapshot(self) -> StateSnapshot:
        """Bygg et fullt StateSnapshot av nåværende tilstand.

        Kalles av PollingWorker med jevn frekvens. I mock-modus
        genereres realistiske, men simulerte verdier.
        """
        now = time.monotonic()
        dt = now - self._last_snapshot_time
        freq = (1.0 / dt) if dt > 1e-6 else 0.0
        self._last_snapshot_time = now

        if self._mock:
            return self._build_mock_snapshot(now, freq)

        assert self._controller is not None
        ctl = self._controller
        pose_ctl = ctl.pose_controller
        safety = ctl.safety_monitor

        pid_gains: dict[Axis, PIDGains] = {}
        if pose_ctl is not None:
            for axis in Axis:
                pid_gains[axis] = pose_ctl.get_pid_gains(axis)

        imu = ctl.base_imu
        imu_accel = imu.read_acceleration() if imu else Vector3(0.0, 0.0, 9.81)
        imu_gyro = imu.read_angular_velocity() if imu else Vector3(0.0, 0.0, 0.0)

        fusion = ctl.imu_fusion
        if fusion is not None:
            ori = fusion.get_orientation()
            orientation = (ori.x, ori.y, ori.z)
        else:
            orientation = (0.0, 0.0, 0.0)

        latest_safety = None
        safety_results: list[SafetyCheckResult] = []
        if safety is not None:
            history = safety.get_check_results()
            safety_results = history
            if history:
                latest_safety = history[-1]

        # PID-feil per akse
        pid_errors: dict[Axis, float] = {}
        if pose_ctl is not None:
            cur = ctl.get_current_pose()
            tgt = ctl.target_pose
            pid_errors = {
                Axis.X: tgt.translation.x - cur.translation.x,
                Axis.Y: tgt.translation.y - cur.translation.y,
                Axis.Z: tgt.translation.z - cur.translation.z,
                Axis.ROLL: tgt.rotation.x - cur.rotation.x,
                Axis.PITCH: tgt.rotation.y - cur.rotation.y,
                Axis.YAW: tgt.rotation.z - cur.rotation.z,
            }

        return StateSnapshot(
            timestamp=time.time(),
            loop_frequency_hz=freq,
            is_running=ctl.is_running(),
            is_e_stopped=safety.is_e_stopped() if safety else False,
            e_stop_reason=safety.e_stop_reason if safety else None,
            current_pose=ctl.get_current_pose(),
            target_pose=ctl.target_pose,
            servo_angles=ctl.get_servo_angles(),
            imu_acceleration=imu_accel,
            imu_angular_velocity=imu_gyro,
            imu_orientation=orientation,
            pid_gains=pid_gains,
            pid_errors=pid_errors,
            latest_safety_result=latest_safety,
            safety_results=safety_results,
        )

    def _build_mock_snapshot(self, now: float, freq: float) -> StateSnapshot:
        """Generer realistisk simulert tilstand for GUI-utvikling."""
        t = now - self._started_at
        # Gyngende bunnplate (simulerer tilt)
        roll = 3.0 * math.sin(0.5 * t)
        pitch = 2.0 * math.cos(0.3 * t)
        yaw = 0.5 * math.sin(0.2 * t)
        current = Pose(
            translation=Vector3(0.0, 0.0, self._config.home_height),
            rotation=Vector3(roll, pitch, yaw),
        )

        # Simulerte servovinkler — følger en sinus rundt home
        servo_angles = [
            90.0 + 10.0 * math.sin(0.4 * t + i * math.pi / 3.0)
            for i in range(6)
        ]

        # Simulert IMU
        accel = Vector3(
            0.2 * math.sin(1.2 * t),
            0.2 * math.cos(1.1 * t),
            9.81 + 0.05 * math.sin(2.0 * t),
        )
        gyro = Vector3(
            5.0 * math.cos(0.5 * t),
            4.0 * math.sin(0.7 * t),
            1.0 * math.cos(0.3 * t),
        )

        # Mock PID-feil
        tgt = self._mock_target_pose
        pid_errors = {
            Axis.X: tgt.translation.x - current.translation.x,
            Axis.Y: tgt.translation.y - current.translation.y,
            Axis.Z: tgt.translation.z - current.translation.z,
            Axis.ROLL: tgt.rotation.x - current.rotation.x,
            Axis.PITCH: tgt.rotation.y - current.rotation.y,
            Axis.YAW: tgt.rotation.z - current.rotation.z,
        }

        # Simuler periodisk sikkerhetssjekk
        mock_safety = SafetyCheckResult(is_safe=True)
        self._mock_safety_results.append(mock_safety)

        return StateSnapshot(
            timestamp=time.time(),
            loop_frequency_hz=freq,
            is_running=self._mock_running,
            is_e_stopped=self._mock_e_stopped,
            e_stop_reason=self._mock_e_stop_reason,
            current_pose=current,
            target_pose=self._mock_target_pose,
            servo_angles=servo_angles,
            imu_acceleration=accel,
            imu_angular_velocity=gyro,
            imu_orientation=(roll, pitch, yaw),
            pid_gains=dict(self._mock_pid_gains),
            pid_errors=pid_errors,
            latest_safety_result=mock_safety,
            safety_results=list(self._mock_safety_results),
        )

    # ------------------------------------------------------------------
    # Kommandoer fra GUI
    # ------------------------------------------------------------------

    def request_start(self) -> None:
        if self._mock:
            self._mock_running = True
            self._log_event("INFO", "Kontrollsløyfe startet")
            return
        if self._controller is not None:
            self._controller.start()
            self._log_event("INFO", "Kontrollsløyfe startet")

    def request_stop(self) -> None:
        if self._mock:
            self._mock_running = False
            self._log_event("INFO", "Kontrollsløyfe stoppet")
            return
        if self._controller is not None:
            self._controller.stop()
            self._log_event("INFO", "Kontrollsløyfe stoppet")

    def request_home(self) -> None:
        home_pose = Pose.home()
        if self._mock:
            self._mock_target_pose = home_pose
            self._log_event("INFO", "Home-posisjon satt")
            self.target_pose_changed.emit(home_pose)
            return
        if self._controller is not None:
            self._controller.home()
            self._log_event("INFO", "Home-posisjon satt")
            # MotionController.home() oppdaterer selv _target_pose. Vi
            # emitterer signalet her slik at GUI-widgets kan synkroniseres.
            self.target_pose_changed.emit(home_pose)

    def set_target_pose(self, pose: Pose) -> bool:
        if self._mock:
            self._mock_target_pose = pose
            self.target_pose_changed.emit(pose)
            return True
        if self._controller is None:
            return False
        ok = self._controller.set_target_pose(pose)
        if ok:
            self.target_pose_changed.emit(pose)
        return ok

    def set_pid_gains(self, axis: Axis, gains: PIDGains) -> bool:
        if self._mock:
            self._mock_pid_gains[axis] = gains
            self.pid_gains_changed.emit(axis, gains)
            return True
        if self._controller is None or self._controller.pose_controller is None:
            return False
        self._controller.pose_controller.set_pid_gains(axis, gains)
        self.pid_gains_changed.emit(axis, gains)
        return True

    def trigger_e_stop(self, reason: str = "") -> None:
        """Stopp sløyfe + frikoble servoer (går via MotionController)."""
        r = reason or "Manuell E-STOP"
        self._log_event("FAIL", f"E-STOP: {r}")
        if self._mock:
            self._mock_e_stopped = True
            self._mock_e_stop_reason = r
            self._mock_running = False
            return
        if self._controller is not None:
            # emergency_stop() frikobler servoer OG kaller trigger_e_stop
            # på safety-monitoren. Vi sender reason via safety-objektet
            # etterpå for å bevare grunnen.
            self._controller.emergency_stop()
            safety = self._controller.safety_monitor
            if safety is not None and reason:
                safety.trigger_e_stop(reason)

    def reset_latched_faults(self) -> bool:
        if self._mock:
            if not self._mock_e_stopped:
                return False
            self._mock_e_stopped = False
            self._mock_e_stop_reason = None
            self._log_event("INFO", "E-STOP tilbakestilt")
            return True
        if self._controller is None or self._controller.safety_monitor is None:
            return False
        ok = self._controller.safety_monitor.reset_latched_faults()
        if ok:
            self._log_event("INFO", "E-STOP tilbakestilt")
        return ok

    # ------------------------------------------------------------------
    # Hendelseslogg
    # ------------------------------------------------------------------

    def _log_event(self, level: str, message: str) -> None:
        """Logg en intern hendelse."""
        self._events.appendleft(BridgeEvent(
            timestamp=time.time(), level=level, message=message,
        ))

    def get_events(self) -> List[BridgeEvent]:
        """Hent siste hendelser (nyeste først)."""
        return list(self._events)

    # ------------------------------------------------------------------
    # Konfigurasjon
    # ------------------------------------------------------------------

    def update_config(self, config: PlatformConfig) -> List[str]:
        """Valider og aktiver ny konfigurasjon ved full reinit av domenet.

        Strukturelle parametere (geometri, I2C-adresser, PWM-frekvens,
        servotabell, loop-rate) er bundet inn i domene-objektene
        (ServoArray, PCA9685Driver, PlatformGeometry, InverseKinematics,
        PoseController) ved initialize(). For å unngå halvt oppdatert
        tilstand bygges hele MotionController på nytt.

        Krever at kontrollsløyfen er stoppet. Returnerer en liste med
        feilmeldinger (tom hvis OK).
        """
        errors = config.validate()
        if errors:
            return errors

        if not self._mock and self._controller is not None and self._controller.is_running():
            return ["Stopp kontrollsløyfen før konfigurasjonen kan endres."]

        self._config = config

        if self._mock:
            # Nullstill mock-tilstand så GUI-et oppfører seg som etter
            # en frisk initialize().
            self._mock_running = False
            self._mock_e_stopped = False
            self._mock_e_stop_reason = None
            self._mock_target_pose = Pose.home()
            self._mock_pid_gains = {
                axis: PIDGains(
                    kp=config.pid_gains.kp,
                    ki=config.pid_gains.ki,
                    kd=config.pid_gains.kd,
                    output_min=config.pid_gains.output_min,
                    output_max=config.pid_gains.output_max,
                    integral_limit=config.pid_gains.integral_limit,
                )
                for axis in Axis
            }
        else:
            try:
                if self._controller is not None:
                    self._controller.shutdown()
                self._controller = MotionController(config)
                self._controller.initialize()
            except Exception as exc:  # noqa: BLE001 — hardware kan feile på mange måter
                self._controller = None
                self._log_event("FAIL", f"Reinit feilet: {exc}")
                return [f"Reinitialisering feilet: {exc}"]

        self._log_event("INFO", "Konfigurasjon aktivert (domenet reinitialisert)")
        self.config_changed.emit(config)
        return []

    def save_config(self) -> bool:
        """Lagre nåværende konfigurasjon til YAML-fil."""
        if self._config is None:
            return False
        try:
            self._config.save(str(self._config_path))
            self._log_event("INFO", f"Konfigurasjon lagret til {self._config_path.name}")
            return True
        except Exception:
            self._log_event("FAIL", "Feil ved lagring av konfigurasjon")
            return False

    def update_safety_limits(self, safety_config: SafetyConfig) -> None:
        """Oppdater sikkerhetsgrenser."""
        if self._config is not None:
            self._config.safety_config = safety_config
        if not self._mock and self._controller is not None:
            safety = self._controller.safety_monitor
            if safety is not None:
                safety.set_limits(safety_config)
        self._log_event("INFO", "Sikkerhetsgrenser oppdatert")

    # ------------------------------------------------------------------
    # IMU-kalibrering
    # ------------------------------------------------------------------

    def calibrate_gyro(self) -> CalibrationResult:
        """Start gyro-kalibrering.

        Returnerer en CalibrationResult slik at GUI kan skille mellom
        "fullført", "ingen IMU", "ikke implementert i driveren" og
        "driveren feilet".
        """
        if self._mock:
            self._log_event("INFO", "Gyro-kalibrering fullført (mock)")
            return CalibrationResult.OK
        if self._controller is None:
            return CalibrationResult.NOT_READY
        imu = self._controller.base_imu
        if imu is None:
            return CalibrationResult.NOT_READY
        try:
            imu.calibrate_gyro_bias()
        except NotImplementedError:
            self._log_event("WARN", "Gyro-kalibrering er ikke implementert i driveren")
            return CalibrationResult.NOT_IMPL
        except Exception as exc:  # noqa: BLE001 — bredt ment
            self._log_event("FAIL", f"Gyro-kalibrering feilet: {exc}")
            return CalibrationResult.FAILED
        self._log_event("INFO", "Gyro-kalibrering fullført")
        return CalibrationResult.OK

    def calibrate_accelerometer(self) -> CalibrationResult:
        """Start akselerometer-kalibrering. Se calibrate_gyro() for retur."""
        if self._mock:
            self._log_event("INFO", "Akselerometer-kalibrering fullført (mock)")
            return CalibrationResult.OK
        if self._controller is None:
            return CalibrationResult.NOT_READY
        imu = self._controller.base_imu
        if imu is None:
            return CalibrationResult.NOT_READY
        try:
            imu.calibrate_accelerometer_offset()
        except NotImplementedError:
            self._log_event(
                "WARN", "Akselerometer-kalibrering er ikke implementert i driveren",
            )
            return CalibrationResult.NOT_IMPL
        except Exception as exc:  # noqa: BLE001 — bredt ment
            self._log_event("FAIL", f"Akselerometer-kalibrering feilet: {exc}")
            return CalibrationResult.FAILED
        self._log_event("INFO", "Akselerometer-kalibrering fullført")
        return CalibrationResult.OK
