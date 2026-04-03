# pose.py
# =======
# Representerer en 6-DOF (6 frihetsgrader) pose for toppplaten.
# Kombinerer translasjon (X, Y, Z) og rotasjon (roll, pitch, yaw)
# til en komplett beskrivelse av plattformens posisjon og orientering.

from __future__ import annotations

import numpy as np

from .vector3 import Vector3


class Pose:
    """6-DOF pose bestående av translasjon og rotasjon.

    Beskriver toppplatens posisjon og orientering relativt til
    bunnplatens senter. Translasjon er i millimeter, rotasjon
    er i grader (roll, pitch, yaw / Euler-vinkler).

    Brukes som mål-pose (hva plattformen skal bevege seg til)
    og som nåværende pose (estimert fra IMU-data).
    """

    def __init__(
        self,
        translation: Vector3 | None = None,
        rotation: Vector3 | None = None,
    ) -> None:
        """Opprett en ny pose.

        Args:
            translation: Posisjon (x, y, z) i millimeter relativt til bunnplatens senter.
                         Standard: origo (0, 0, 0).
            rotation: Orientering (roll, pitch, yaw) i grader.
                      Standard: ingen rotasjon (0, 0, 0).
        """
        self.translation = translation or Vector3()
        self.rotation = rotation or Vector3()

    def to_matrix(self) -> np.ndarray:
        """Konverter posen til en 4x4 homogen transformasjonsmatrise.

        Bruker ZYX Euler-vinkelkonvensjon (yaw -> pitch -> roll)
        for rotasjon, kombinert med translasjonen.

        Returns:
            4x4 numpy matrise som representerer transformasjonen.
        """
        # Euler-vinkler i radianer (ZYX-konvensjon)
        roll = np.radians(self.rotation.x)
        pitch = np.radians(self.rotation.y)
        yaw = np.radians(self.rotation.z)

        cr, sr = np.cos(roll), np.sin(roll)
        cp, sp = np.cos(pitch), np.sin(pitch)
        cy, sy = np.cos(yaw), np.sin(yaw)

        # ZYX rotasjonsmatrise: Rz(yaw) * Ry(pitch) * Rx(roll)
        m = np.eye(4)
        m[0, 0] = cy * cp
        m[0, 1] = cy * sp * sr - sy * cr
        m[0, 2] = cy * sp * cr + sy * sr
        m[1, 0] = sy * cp
        m[1, 1] = sy * sp * sr + cy * cr
        m[1, 2] = sy * sp * cr - cy * sr
        m[2, 0] = -sp
        m[2, 1] = cp * sr
        m[2, 2] = cp * cr

        m[0, 3] = self.translation.x
        m[1, 3] = self.translation.y
        m[2, 3] = self.translation.z

        return m

    @classmethod
    def from_matrix(cls, m: np.ndarray) -> Pose:
        """Opprett en Pose fra en 4x4 homogen transformasjonsmatrise.

        Ekstraherer translasjon og Euler-vinkler (ZYX-konvensjon)
        fra matrisen.

        Args:
            m: 4x4 homogen transformasjonsmatrise.

        Returns:
            Ny Pose-instans.
        """
        tx = float(m[0, 3])
        ty = float(m[1, 3])
        tz = float(m[2, 3])

        # Ekstraher Euler-vinkler fra ZYX rotasjonsmatrise
        pitch = np.arctan2(-m[2, 0], np.sqrt(m[0, 0] ** 2 + m[1, 0] ** 2))
        cp = np.cos(pitch)

        if abs(cp) > 1e-6:
            roll = np.arctan2(m[2, 1] / cp, m[2, 2] / cp)
            yaw = np.arctan2(m[1, 0] / cp, m[0, 0] / cp)
        else:
            # Gimbal lock — pitch ≈ ±90°
            roll = np.arctan2(m[0, 1], m[1, 1])
            yaw = 0.0

        return cls(
            translation=Vector3(tx, ty, tz),
            rotation=Vector3(
                float(np.degrees(roll)),
                float(np.degrees(pitch)),
                float(np.degrees(yaw)),
            ),
        )

    def interpolate(self, other: Pose, t: float) -> Pose:
        """Lineær interpolasjon mellom denne posen og en annen.

        Nyttig for å generere jevne bevegelser mellom to posisjoner.

        Args:
            other: Mål-posen å interpolere mot.
            t: Interpolasjonsfaktor (0.0 = denne posen, 1.0 = other).

        Returns:
            Ny interpolert pose.
        """
        trans = self.translation + (other.translation - self.translation) * t
        rot = self.rotation + (other.rotation - self.rotation) * t
        return Pose(translation=trans, rotation=rot)

    def is_within_bounds(self, max_translation: float, max_rotation: float) -> bool:
        """Sjekk om posen er innenfor gitte grenser.

        Brukes av SafetyMonitor for å verifisere at en pose
        ikke overskrider maksimale bevegelsesgrenser.

        Args:
            max_translation: Maksimal avstand fra origo i mm.
            max_rotation: Maksimal rotasjon fra nøytral i grader.

        Returns:
            True hvis posen er innenfor grensene.
        """
        if self.translation.magnitude() > max_translation:
            return False
        if self.rotation.magnitude() > max_rotation:
            return False
        return True

    @classmethod
    def home(cls) -> Pose:
        """Opprett en hjemmepose (alle verdier null).

        Hjemmeposen representerer plattformens nøytralposisjon
        der toppplaten er sentrert og vannrett.

        Returns:
            Pose med translasjon og rotasjon satt til (0, 0, 0).
        """
        return cls()

    def __repr__(self) -> str:
        """Tekstrepresentasjon for feilsøking."""
        return (
            f"Pose(translation={self.translation}, "
            f"rotation={self.rotation})"
        )
