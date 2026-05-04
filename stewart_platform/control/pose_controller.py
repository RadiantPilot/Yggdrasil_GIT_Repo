# pose_controller.py
# ==================
# Posekontroller med 3 PID-regulatorer (én per rotasjonsakse).
# Beregner en korrigert orientering basert på avviket mellom
# ønsket og målt orientering (fra IMU-fusjon).

from __future__ import annotations

from ..config.platform_config import Axis, PIDGains
from ..geometry.pose import Pose
from ..geometry.vector3 import Vector3
from .pid_controller import PIDController


class PoseController:
    """3-DOF orienteringskontroller med PID per akse.

    Bruker tre uavhengige PID-regulatorer for ROLL, PITCH og YAW.
    Utgangen er target + PID-korreksjon — sendes videre til IK.
    """

    def __init__(self, gains: PIDGains) -> None:
        self._controllers = [PIDController(gains) for _ in range(3)]

    def update(self, target: Pose, current: Pose, dt: float) -> Pose:
        """Beregn kommandert orientering = target + PID-korreksjon.

        Når plattformen allerede er der den skal være blir
        korreksjonen null og kommandert pose lik target.
        """
        setpoints = [target.rotation.x, target.rotation.y, target.rotation.z]
        measurements = [current.rotation.x, current.rotation.y, current.rotation.z]
        corrections = [
            self._controllers[i].update(setpoints[i], measurements[i], dt)
            for i in range(3)
        ]
        return Pose(
            rotation=Vector3(
                setpoints[0] + corrections[0],
                setpoints[1] + corrections[1],
                setpoints[2] + corrections[2],
            ),
        )

    def reset(self) -> None:
        """Nullstill alle PID-regulatorer."""
        for controller in self._controllers:
            controller.reset()

    def get_pid_gains(self, axis: Axis) -> PIDGains:
        """Hent PID-forsterkning for en akse."""
        return self._controllers[int(axis)]._gains

    def set_pid_gains(self, axis: Axis, gains: PIDGains) -> None:
        """Sett PID-forsterkning for én akse."""
        self._controllers[int(axis)].set_gains(gains)

    def set_gains(self, gains: PIDGains) -> None:
        """Oppdater forsterkningene for alle tre akser."""
        for controller in self._controllers:
            controller.set_gains(gains)
