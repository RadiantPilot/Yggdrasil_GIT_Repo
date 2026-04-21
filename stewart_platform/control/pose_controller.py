# pose_controller.py
# ==================
# Posekontroller som bruker 6 PID-regulatorer (en per frihetsgrad)
# for å beregne en korrigert pose basert på avviket mellom
# ønsket pose (setpunkt) og målt pose (fra IMU-fusjon).

from __future__ import annotations

from typing import Callable, List, Optional

from ..config.platform_config import Axis, PIDGains
from ..geometry.pose import Pose
from .pid_controller import PIDController


class StepResponseRecorder:
    """Samler step-respons-data for en enkelt akse.

    Brukes av PoseController for å registrere setpunkt og
    faktisk verdi per tick under et step-respons-eksperiment.
    GUI kan polle get_step_response_recorder() for å lese bufferen.
    """

    def __init__(self, axis: Axis, from_val: float, to_val: float) -> None:
        """Opprett en ny recorder for en step-respons.

        Args:
            axis: Aksen som stepes.
            from_val: Startverdi for steppet.
            to_val: Sluttverdi (nytt setpunkt).
        """
        self.axis = axis
        self.from_val = from_val
        self.to_val = to_val
        self.is_active = True
        self.samples: List[tuple[float, float, float]] = []

    def record(self, timestamp: float, setpoint: float, actual: float) -> None:
        """Legg til en sample i bufferen.

        Ignorerer kall hvis recorder allerede er avsluttet.

        Args:
            timestamp: Tidspunkt for samplen i sekunder.
            setpoint: Setpunktverdi for aksen.
            actual: Faktisk målt verdi for aksen.
        """
        if not self.is_active:
            return
        self.samples.append((timestamp, setpoint, actual))

    def finish(self) -> None:
        """Marker step-responsen som avsluttet."""
        self.is_active = False


# Type-alias for response-lytter-callback.
ResponseListener = Callable[[Axis, float, float, float], None]


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
        For å bruke ulike forsterkninger per akse, bruk set_pid_gains()
        individuelt etter opprettelse.

        Args:
            gains: PID-forsterkning som brukes for alle 6 akser.
        """
        self._controllers = [PIDController(gains) for _ in range(6)]
        self._step_recorders: dict[Axis, StepResponseRecorder] = {}
        self._response_listeners: List[ResponseListener] = []

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

    def get_pid_gains(self, axis: Axis) -> PIDGains:
        """Hent PID-forsterkning for en enkelt akse.

        Args:
            axis: Frihetsgraden (X, Y, Z, ROLL, PITCH, YAW).

        Returns:
            PIDGains for den valgte aksen.

        Raises:
            IndexError: Hvis axis-verdien er utenfor 0-5.
        """
        idx = int(axis)
        return self._controllers[idx]._gains

    def set_pid_gains(self, axis: Axis, gains: PIDGains) -> None:
        """Sett PID-forsterkning for en enkelt akse.

        Tillater individuell tuning per frihetsgrad uten
        å påvirke de andre aksene.

        Args:
            axis: Frihetsgraden som skal oppdateres.
            gains: Nye PID-forsterkningsverdier for den valgte aksen.

        Raises:
            IndexError: Hvis axis-verdien er utenfor 0-5.
        """
        idx = int(axis)
        self._controllers[idx].set_gains(gains)

    def set_gains(self, gains: PIDGains) -> None:
        """Oppdater forsterkningsparametrene for alle 6 akser.

        Args:
            gains: Nye PID-forsterkningsverdier.
        """
        for controller in self._controllers:
            controller.set_gains(gains)

    def trigger_step_response(
        self, axis: Axis, from_val: float, to_val: float
    ) -> None:
        """Start et step-respons-eksperiment på en akse.

        Oppretter en StepResponseRecorder som samler data
        (tidspunkt, setpunkt, faktisk verdi) per tick.

        Eventuell tidligere aktiv recorder for samme akse
        avsluttes automatisk.

        Args:
            axis: Aksen som skal stepes.
            from_val: Startverdi for steppet.
            to_val: Ny setpunktverdi.
        """
        # Avslutt eventuell aktiv recorder for denne aksen
        old = self._step_recorders.get(axis)
        if old is not None and old.is_active:
            old.finish()
        self._step_recorders[axis] = StepResponseRecorder(axis, from_val, to_val)

    def get_step_response_recorder(
        self, axis: Axis
    ) -> Optional[StepResponseRecorder]:
        """Hent step-respons-recorder for en akse.

        Brukes av GUI polling worker for å lese step-respons-data.

        Args:
            axis: Aksen å hente recorder for.

        Returns:
            StepResponseRecorder eller None hvis ingen er aktiv.
        """
        return self._step_recorders.get(axis)

    def add_response_listener(self, callback: ResponseListener) -> None:
        """Registrer en lytter for step-respons-samples.

        Lytteren kalles med (axis, timestamp, setpoint, actual) for
        hvert sample som registreres under et aktivt step-respons-
        eksperiment.

        Args:
            callback: Funksjon som kalles med sample-data.
        """
        self._response_listeners.append(callback)

    def remove_response_listener(self, callback: ResponseListener) -> None:
        """Fjern en tidligere registrert lytter.

        Args:
            callback: Lytteren som skal fjernes.
        """
        self._response_listeners.remove(callback)

    def _notify_listeners(
        self, axis: Axis, timestamp: float, setpoint: float, actual: float
    ) -> None:
        """Varsle alle registrerte lyttere om en ny sample."""
        for listener in self._response_listeners:
            listener(axis, timestamp, setpoint, actual)
