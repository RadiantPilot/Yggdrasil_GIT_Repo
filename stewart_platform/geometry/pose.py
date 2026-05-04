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
        """Lineær interpolasjon mellom to orienteringer."""
        rot = self.rotation + (other.rotation - self.rotation) * t
        return Pose(rotation=rot)

    @classmethod
    def home(cls) -> Pose:
        """Hvilestilling — null rotasjon."""
        return cls()

    def __repr__(self) -> str:
        return f"Pose(rotation={self.rotation})"
