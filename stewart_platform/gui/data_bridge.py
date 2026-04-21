# data_bridge.py
# ==============
# Tradsikker bro mellom GUI-trad og kontrolltrad.
# Gir GUI-en tilgang til sanntidsdata fra MotionController
# uten direkte tilgang til maskinvare eller kontrollsloeyfe.

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

from ..geometry.pose import Pose
from ..geometry.vector3 import Vector3
from ..safety.safety_monitor import SafetyCheckResult, SafetySeverity

if TYPE_CHECKING:
    from ..control.motion_controller import MotionController


@dataclass
class GUIState:
    """Snapshot av all tilstand GUI-en trenger.

    Oppdateres fra kontrolltrad og leses fra GUI-trad.
    Alle verdier er kopier — trygt a lese uten laas.
    """
    current_pose: Pose = field(default_factory=Pose.home)
    target_pose: Pose = field(default_factory=Pose.home)
    servo_angles: List[float] = field(default_factory=lambda: [90.0] * 6)
    is_running: bool = False
    is_e_stopped: bool = False
    safety_result: SafetyCheckResult = field(default_factory=SafetyCheckResult)
    imu_accel: Vector3 = field(default_factory=Vector3)
    imu_gyro: Vector3 = field(default_factory=Vector3)
    orientation: Vector3 = field(default_factory=Vector3)


class GUIDataBridge:
    """Tradsikker bro mellom kontrollsloeyfe og GUI.

    Kontrolltraden kaller update_from_controller() etter hvert steg.
    GUI-traden kaller get_state() for a hente siste tilstand.
    Kommandoer fra GUI sendes via set_target_pose() osv.
    """

    def __init__(self) -> None:
        """Opprett data bridge med standardtilstand."""
        self._lock = threading.Lock()
        self._state = GUIState()
        self._controller: Optional[MotionController] = None

    def connect(self, controller: MotionController) -> None:
        """Koble data bridge til en MotionController.

        Args:
            controller: Kontrolleren som skal overvakes.
        """
        self._controller = controller

    def update_from_controller(self) -> None:
        """Oppdater tilstand fra kontrolleren. Kalles fra kontrolltrad."""
        ctrl = self._controller
        if ctrl is None:
            return

        with self._lock:
            self._state.current_pose = ctrl.get_current_pose()
            self._state.target_pose = ctrl.target_pose
            self._state.servo_angles = ctrl.get_servo_angles() or [90.0] * 6
            self._state.is_running = ctrl.is_running()

            if ctrl.safety_monitor is not None:
                self._state.is_e_stopped = (
                    ctrl.safety_monitor.is_e_stopped()
                )

            if ctrl.base_imu is not None:
                try:
                    self._state.imu_accel = ctrl.base_imu.read_acceleration()
                    self._state.imu_gyro = ctrl.base_imu.read_angular_velocity()
                except Exception:
                    pass

            if ctrl.imu_fusion is not None:
                self._state.orientation = ctrl.imu_fusion.get_orientation()

    def get_state(self) -> GUIState:
        """Hent siste tilstandssnapshot. Kalles fra GUI-trad.

        Returns:
            Kopi av navaerende GUIState.
        """
        with self._lock:
            return GUIState(
                current_pose=self._state.current_pose,
                target_pose=self._state.target_pose,
                servo_angles=list(self._state.servo_angles),
                is_running=self._state.is_running,
                is_e_stopped=self._state.is_e_stopped,
                safety_result=self._state.safety_result,
                imu_accel=self._state.imu_accel,
                imu_gyro=self._state.imu_gyro,
                orientation=self._state.orientation,
            )

    def set_target_pose(self, pose: Pose) -> str:
        """Sett ny mal-pose fra GUI. Kalles fra GUI-trad.

        Args:
            pose: Onsket 6-DOF pose.

        Returns:
            Tom streng ved suksess, feilmelding ved feil.
        """
        ctrl = self._controller
        if ctrl is None:
            return "Kontroller ikke tilkoblet."
        try:
            ctrl.set_target_pose(pose)
            return ""
        except ValueError as e:
            return str(e)

    def start(self) -> None:
        """Start kontrollsloeyfen."""
        if self._controller is not None:
            self._controller.start()

    def stop(self) -> None:
        """Stopp kontrollsloeyfen."""
        if self._controller is not None:
            self._controller.stop()

    def emergency_stop(self) -> None:
        """Utlos nodstopp."""
        if self._controller is not None:
            self._controller.emergency_stop()

    def reset_latched_faults(self) -> None:
        """Tilbakestill nodstopp og latchede feil."""
        ctrl = self._controller
        if ctrl is not None and ctrl.safety_monitor is not None:
            ctrl.safety_monitor.reset_latched_faults()

    @property
    def is_connected(self) -> bool:
        """Sjekk om data bridge er koblet til en kontroller."""
        return self._controller is not None
