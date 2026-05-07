# pose.py
# =======
# Representerer plattformens orientering (roll, pitch, yaw).
# Stewart-plattformen styres nå kun rotasjonelt — toppplaten holdes
# på fast home_height og kan kun roteres rundt sentrumspunktet.

from __future__ import annotations

from .vector3 import Vector3


class Pose:
    """Plattformens orientering som tre Euler-vinkler (grader).

    Brukes både som mål (hva vi styrer mot) og som målt verdi
    (estimert fra IMU-fusjon). Konvensjon: x=roll, y=pitch, z=yaw.
    """

    def __init__(self, rotation: Vector3 | None = None) -> None:
        self.rotation = rotation or Vector3()

    def is_within_bounds(self, max_rotation_deg: float) -> bool:
        """True hvis |rotation| ≤ max_rotation_deg."""
        return self.rotation.magnitude() <= max_rotation_deg

    def interpolate(self, other: Pose, t: float) -> Pose:
        """Sferisk lineær interpolasjon mellom to orienteringer.

        Interpolerer beløp og retning separat for å unngå feil
        ved store rotasjoner (> ~5°) som ren lineær interpolasjon gir.
        """
        mag_self = self.rotation.magnitude()
        mag_other = other.rotation.magnitude()
        mag = mag_self + (mag_other - mag_self) * t
        if mag_self < 1e-10:
            rot = other.rotation * t
        elif mag_other < 1e-10:
            rot = self.rotation * (1.0 - t)
        else:
            dir_self = self.rotation * (1.0 / mag_self)
            dir_other = other.rotation * (1.0 / mag_other)
            dir_interp = dir_self + (dir_other - dir_self) * t
            dir_mag = dir_interp.magnitude()
            rot = dir_interp * (mag / dir_mag) if dir_mag >= 1e-10 else Vector3()
        return Pose(rotation=rot)

    @classmethod
    def home(cls) -> Pose:
        """Hvilestilling — null rotasjon."""
        return cls()

    def __repr__(self) -> str:
        return f"Pose(rotation={self.rotation})"
