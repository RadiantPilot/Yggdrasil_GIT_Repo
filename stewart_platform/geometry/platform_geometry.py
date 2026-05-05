# platform_geometry.py
# ====================
# Geometrisk modell av Stewart-plattformens fysiske dimensjoner.
# Beregner posisjonen til de 6 leddpunktene på bunnplaten og
# toppplaten, samt beinvektorer og beinlengder for en gitt pose.
# Alle geometriske parametere leses fra PlatformConfig.

from __future__ import annotations

import math
from typing import List, TYPE_CHECKING

import numpy as np

from .vector3 import Vector3
from .pose import Pose

if TYPE_CHECKING:
    from ..config.platform_config import PlatformConfig


class PlatformGeometry:
    """Geometrisk modell av Stewart-plattformen.

    Beregner posisjonene til de 6 leddpunktene (joints) på
    bunnplaten og toppplaten basert på radius og vinkler fra
    konfigurasjonen. Leddpunktene er plassert på en sirkel med
    gitt radius, og vinklene bestemmer deres posisjon på sirkelen.

    Denne klassen er kjernen i den geometriske modellen som
    InverseKinematics-solveren bruker for å beregne servovinkler.
    """

    def __init__(self, config: PlatformConfig) -> None:
        """Opprett en geometrisk modell fra konfigurasjon.

        Beregner og cacher leddposisjonene for bunnplaten og
        toppplaten (i lokalt koordinatsystem) ved opprettelse.

        Args:
            config: Plattformkonfigurasjon med geometriske parametere.
        """
        self._base_radius = config.base_radius
        self._platform_radius = config.platform_radius
        self._base_joint_angles = config.base_joint_angles
        self._platform_joint_angles = config.platform_joint_angles
        self._servo_horn_length = config.servo_horn_length
        self._rod_length = config.rod_length
        # Forhåndsberegn leddposisjoner
        self._base_joints = self._compute_circle_joints(
            self._base_radius, self._base_joint_angles
        )
        self._platform_joints_local = self._compute_circle_joints(
            self._platform_radius, self._platform_joint_angles
        )
        # Bruk eksplisitt home_height fra config hvis satt; ellers
        # avled fra geometri slik at YAML kan utelate feltet.
        if config.home_height is None:
            self._home_height = self.compute_home_height()
        else:
            self._home_height = config.home_height

    @staticmethod
    def _compute_circle_joints(radius: float, angles_deg: List[float]) -> List[Vector3]:
        """Beregn leddposisjoner på en sirkel i XY-planet."""
        joints: List[Vector3] = []
        for angle_deg in angles_deg:
            angle_rad = math.radians(angle_deg)
            joints.append(Vector3(
                radius * math.cos(angle_rad),
                radius * math.sin(angle_rad),
                0.0,
            ))
        return joints

    def get_base_joint_angles(self) -> List[float]:
        """Hent vinklene (i grader) for de 6 leddpunktene på bunnplaten.

        Brukes f.eks. av InverseKinematics for å beregne servoens
        effektive monteringsvinkel.

        Returns:
            Kopi av listen med 6 vinkler i grader.
        """
        return list(self._base_joint_angles)

    def get_servo_horn_length(self) -> float:
        """Hent servoarm-lengden i millimeter."""
        return self._servo_horn_length

    def get_rod_length(self) -> float:
        """Hent stag-lengden i millimeter."""
        return self._rod_length

    def get_home_height(self) -> float:
        """Hent hvilehøyden i millimeter (eksplisitt eller avledet)."""
        return self._home_height

    def get_base_joints(self) -> List[Vector3]:
        """Hent posisjonene til de 6 leddpunktene på bunnplaten.

        Leddpunktene er plassert på en sirkel med radius
        base_radius, med vinkler gitt av base_joint_angles.
        Alle posisjoner er i bunnplatens koordinatsystem (Z=0).

        Returns:
            Liste med 6 Vector3-posisjoner (x, y, 0) i millimeter.
        """
        return list(self._base_joints)

    def get_platform_joints_local(self) -> List[Vector3]:
        """Hent leddposisjonene på toppplaten i lokalt koordinatsystem.

        Posisjonene er relativt til toppplatens eget senter,
        før transformasjon med en pose. Brukes som utgangspunkt
        for å beregne verdensposisjoner via get_platform_joints_world().

        Returns:
            Liste med 6 Vector3-posisjoner i millimeter.
        """
        return list(self._platform_joints_local)

    def get_platform_joints_world(self, pose: Pose) -> List[Vector3]:
        """Beregn toppplatens leddposisjoner i verdenskoordinater.

        Transformerer de lokale leddposisjonene med pose-rotasjonen
        og en fast translasjon (0, 0, home_height). Plattformen kan
        kun rotere — translasjon er fjernet fra modellen.
        """
        rot = self._rotation_matrix(pose.rotation)
        translation = np.array([0.0, 0.0, self._home_height])

        world_joints: List[Vector3] = []
        for joint in self._platform_joints_local:
            local = joint.to_array()
            world = rot @ local + translation
            world_joints.append(Vector3.from_array(world))
        return world_joints

    @staticmethod
    def _rotation_matrix(rotation: Vector3) -> np.ndarray:
        """Bygg 3x3 ZYX-rotasjonsmatrise fra Euler-vinkler i grader."""
        roll = math.radians(rotation.x)
        pitch = math.radians(rotation.y)
        yaw = math.radians(rotation.z)
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        return np.array([
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp,     cp * sr,                cp * cr],
        ])

    def get_leg_vectors(self, pose: Pose) -> List[Vector3]:
        """Beregn beinvektorene fra bunnplate-ledd til toppplate-ledd.

        Hver beinvektor går fra servoens tilkoblingspunkt på
        bunnplaten til det korresponderende leddpunktet på toppplaten.

        Args:
            pose: Ønsket pose for toppplaten.

        Returns:
            Liste med 6 Vector3 beinvektorer i millimeter.
        """
        world_joints = self.get_platform_joints_world(pose)
        base_joints = self._base_joints
        return [world_joints[i] - base_joints[i] for i in range(6)]

    def get_leg_lengths(self, pose: Pose) -> List[float]:
        """Beregn beinlengdene for en gitt pose.

        Beinlengden er avstanden mellom bunnplate-leddet og
        toppplate-leddet for hvert av de 6 beinene.
        Brukes av InverseKinematics for å beregne servovinkler.

        Args:
            pose: Ønsket pose for toppplaten.

        Returns:
            Liste med 6 beinlengder i millimeter.
        """
        leg_vectors = self.get_leg_vectors(pose)
        return [v.magnitude() for v in leg_vectors]

    def compute_home_height(self) -> float:
        """Beregn hvilehøyden basert på geometrien.

        Beregner den nøytrale høyden der alle bein har lik lengde
        og servoene er i hjemmeposisjon. Nyttig som startpunkt
        for justering.

        Returns:
            Hvilehøyde i millimeter.
        """
        # Ved hjemmeposisjon: beinlengde = rod_length
        # Horisontal avstand mellom ledd = |platform_joint - base_joint| i XY
        # Vertikal komponent: h = sqrt(rod_length² - horisontalt²)
        b = self._base_joints[0]
        p = self._platform_joints_local[0]
        dx = p.x - b.x
        dy = p.y - b.y
        horisontalt_sq = dx ** 2 + dy ** 2
        radicand = self._rod_length ** 2 - horisontalt_sq
        if radicand <= 0:
            raise ValueError(
                f"Geometrifeil: stag-lengde ({self._rod_length:.1f} mm) er for kort til å nå "
                f"plattform-leddet (horisontal avstand {math.sqrt(horisontalt_sq):.1f} mm). "
                "Sjekk rod_length, base_radius, og platform_radius i konfigurasjonen."
            )
        return math.sqrt(radicand)
