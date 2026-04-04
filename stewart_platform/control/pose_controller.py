# pose_controller.py
# ==================
# Posekontroller som bruker 6 PID-regulatorer (en per frihetsgrad)
# for å beregne en korrigert pose basert på avviket mellom
# ønsket pose (setpunkt) og målt pose (fra IMU-fusjon).

from __future__ import annotations

from ..config.platform_config import PIDGains
from ..geometry.pose import Pose
from .pid_controller import PIDController


class PoseController:
    """6-DOF posekontroller med individuelle PID-regulatorer.

    Bruker 6 uavhengige PID-regulatorer — en for hver frihetsgrad
    (X, Y, Z, roll, pitch, yaw) — for å minimere avviket mellom
    ønsket pose og nåværende pose. Utgangen er en korrigert pose
    som kan sendes til InverseKinematics.

    Rekkefølge: [X, Y, Z, roll, pitch, yaw]
    """

    def __init__(self, gains: PIDGains) -> None:
        """Opprett en posekontroller med 6 PID-regulatorer.

        Alle 6 regulatorene initialiseres med samme forsterkning.
        For å bruke ulike forsterkninger per akse, bruk set_gains()
        individuelt etter opprettelse.

        Args:
            gains: PID-forsterkning som brukes for alle 6 akser.
        """
        self._controllers = [PIDController(gains) for _ in range(6)]

    def update(self, target: Pose, current: Pose, dt: float) -> Pose:
        """Beregn korrigert pose basert på avviket mellom mål og nåværende pose.

        Kjører alle 6 PID-regulatorer med forskjellen mellom
        target og current som feil, og returnerer en ny pose
        som representerer den nødvendige korreksjonen.

        Args:
            target: Ønsket mål-pose.
            current: Nåværende estimert pose (fra IMU-fusjon).
            dt: Tid siden forrige oppdatering i sekunder.

        Returns:
            Korrigert pose som kan sendes til IK-solveren.
        """
        from ..geometry.vector3 import Vector3

        setpoints = [
            target.translation.x, target.translation.y, target.translation.z,
            target.rotation.x, target.rotation.y, target.rotation.z,
        ]
        measurements = [
            current.translation.x, current.translation.y, current.translation.z,
            current.rotation.x, current.rotation.y, current.rotation.z,
        ]
        outputs = [
            self._controllers[i].update(setpoints[i], measurements[i], dt)
            for i in range(6)
        ]
        return Pose(
            translation=Vector3(outputs[0], outputs[1], outputs[2]),
            rotation=Vector3(outputs[3], outputs[4], outputs[5]),
        )

    def reset(self) -> None:
        """Nullstill alle 6 PID-regulatorer.

        Kalles ved oppstart eller etter nødstopp.
        """
        for controller in self._controllers:
            controller.reset()

    def set_gains(self, gains: PIDGains) -> None:
        """Oppdater forsterkningsparametrene for alle 6 akser.

        Args:
            gains: Nye PID-forsterkningsverdier.
        """
        for controller in self._controllers:
            controller.set_gains(gains)
