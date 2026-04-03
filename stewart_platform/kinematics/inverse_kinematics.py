# inverse_kinematics.py
# =====================
# Invers kinematikk-solver for Stewart-plattformen.
# Gitt en ønsket 6-DOF pose (translasjon + rotasjon), beregner
# denne klassen de 6 servovinklene som trengs for å oppnå posen.
# Dette er det matematiske hjertet i styringssystemet.

from __future__ import annotations

import math
from typing import List, Tuple

from ..config.platform_config import ServoConfig
from ..geometry.platform_geometry import PlatformGeometry
from ..geometry.pose import Pose
from ..geometry.vector3 import Vector3


class InverseKinematics:
    """Invers kinematikk-solver for Stewart-plattformen.

    Tar en ønsket 6-DOF pose og beregner hvilke vinkler de 6
    servomotorene må stå i for å oppnå den posen. Bruker
    plattformens geometriske modell og servokonfigurasjon
    (armlengde, monteringsvinkel) for beregningene.

    Algoritmen:
    1. Beregn toppplatens leddposisjoner i verdenskoordinater.
    2. Beregn beinvektorer fra bunnplate-ledd til toppplate-ledd.
    3. Beregn nødvendig servovinkel for hvert bein basert på
       servoarmens lengde og beinets lengde.
    """

    def __init__(
        self,
        geometry: PlatformGeometry,
        servo_configs: List[ServoConfig],
    ) -> None:
        """Opprett en IK-solver med gitt geometri og servokonfigurasjon.

        Args:
            geometry: Geometrisk modell av plattformen.
            servo_configs: Liste med 6 servoinnstillinger (armlengde,
                          monteringsvinkel, grenser).
        """
        self._geometry = geometry
        self._servo_configs = servo_configs

    def solve(self, pose: Pose) -> List[float]:
        """Løs invers kinematikk for en gitt pose.

        Beregner de 6 servovinklene som plasserer toppplaten
        i den ønskede posisjonen og orienteringen.

        Args:
            pose: Ønsket 6-DOF pose for toppplaten.

        Returns:
            Liste med 6 servovinkler i grader.

        Raises:
            ValueError: Hvis posen ikke er oppnåelig (f.eks.
                        beinlengden overskrider fysiske grenser).
        """
        leg_vectors = self._geometry.get_leg_vectors(pose)
        angles: List[float] = []

        for i, leg_vec in enumerate(leg_vectors):
            angle = self._leg_length_to_servo_angle(leg_vec, i)
            sc = self._servo_configs[i]
            if not (sc.min_angle_deg <= angle <= sc.max_angle_deg):
                raise ValueError(
                    f"Servo {i}: beregnet vinkel {angle:.1f}° er utenfor "
                    f"grensene [{sc.min_angle_deg}, {sc.max_angle_deg}]."
                )
            angles.append(angle)

        return angles

    def _compute_leg_lengths(self, pose: Pose) -> List[float]:
        """Beregn beinlengder for en gitt pose.

        Hjelpemetode som bruker PlatformGeometry til å finne
        avstanden mellom hvert par av bunn- og toppledd.

        Args:
            pose: Ønsket pose.

        Returns:
            Liste med 6 beinlengder i millimeter.
        """
        return self._geometry.get_leg_lengths(pose)

    def _leg_length_to_servo_angle(
        self,
        leg_vector: Vector3,
        servo_index: int,
    ) -> float:
        """Konverter en beinvektor til servovinkel.

        Bruker geometrisk analyse av servohornets lengde,
        staglengden og beinvektoren for å beregne servovinkelen
        som gir riktig beinlengde. Tar hensyn til servoens
        monteringsvinkel og rotasjonsretning.

        Geometri: Servohornet roterer i en vertikal plan definert av
        monteringsvinkelen. Stangen forbinder hornspissen med
        toppplate-leddet. Vi løser for servovinkelen α slik at
        |hornspiss - toppledd| = rod_length.

        Args:
            leg_vector: Vektor fra bunnledd til toppledd (mm).
            servo_index: Indeks for servoen (0-5).

        Returns:
            Servovinkel i grader.
        """
        sc = self._servo_configs[servo_index]
        mount_rad = math.radians(sc.mounting_angle_deg)
        a = self._geometry._servo_horn_length
        s = self._geometry._rod_length

        # Dekomponér beinvektor i servoens lokale koordinater
        L_r = leg_vector.x * math.cos(mount_rad) + leg_vector.y * math.sin(mount_rad)
        L_z = leg_vector.z

        # Total beinlengde (3D)
        d_sq = leg_vector.x ** 2 + leg_vector.y ** 2 + leg_vector.z ** 2

        # Likning: d² + a² - s² = 2a(L_r·cos(α) + L_z·sin(α))
        M = (d_sq + a ** 2 - s ** 2) / (2.0 * a)

        # R·cos(α - φ) = M der R = sqrt(L_r² + L_z²), φ = atan2(L_z, L_r)
        R = math.sqrt(L_r ** 2 + L_z ** 2)
        if R < 1e-10:
            raise ValueError("Beinvektor har null lengde i servoplanet.")

        cos_val = M / R
        if abs(cos_val) > 1.0:
            raise ValueError(
                f"Pose er ikke oppnåelig for servo {servo_index}: "
                f"cos = {cos_val:.4f}."
            )

        phi = math.atan2(L_z, L_r)
        alpha = phi + math.acos(cos_val)

        # Anvend servoens retning
        angle_deg = math.degrees(alpha)
        if sc.direction == -1:
            angle_deg = 180.0 - angle_deg

        return angle_deg

    def is_pose_reachable(self, pose: Pose) -> bool:
        """Sjekk om en pose er fysisk oppnåelig.

        Verifiserer at alle 6 beinlengder og servovinkler er
        innenfor fysiske og mekaniske grenser. Sjekker blant annet:
        - Beinlengde innenfor (rod_length - horn_length) og (rod_length + horn_length).
        - Servovinkler innenfor min_angle_deg og max_angle_deg.

        Args:
            pose: Posen som skal sjekkes.

        Returns:
            True hvis posen kan oppnås.
        """
        try:
            self.solve(pose)
            return True
        except ValueError:
            return False

    def get_workspace_bounds(self) -> Tuple[Pose, Pose]:
        """Estimer arbeidsområdets grenser.

        Beregner en tilnærming av minimums- og maksimums-posen
        (translasjon og rotasjon) som plattformen kan oppnå.
        Nyttig for å sette opp SafetyConfig-grenser.

        Returns:
            Tuple med (min_pose, max_pose) som beskriver
            det omtrentlige arbeidsområdet.
        """
        # Binærsøk for maksimal translasjon/rotasjon langs hver akse
        def _max_along(axis: str, direction: float) -> float:
            lo, hi = 0.0, 200.0
            for _ in range(50):
                mid = (lo + hi) / 2.0
                kwargs_t = {"x": 0.0, "y": 0.0, "z": 0.0}
                kwargs_r = {"x": 0.0, "y": 0.0, "z": 0.0}
                if axis in ("tx", "ty", "tz"):
                    kwargs_t[axis[1]] = mid * direction
                else:
                    kwargs_r[axis[1]] = mid * direction
                pose = Pose(
                    translation=Vector3(**kwargs_t),
                    rotation=Vector3(**kwargs_r),
                )
                if self.is_pose_reachable(pose):
                    lo = mid
                else:
                    hi = mid
            return lo * direction

        min_trans = Vector3(
            _max_along("tx", -1.0),
            _max_along("ty", -1.0),
            _max_along("tz", -1.0),
        )
        max_trans = Vector3(
            _max_along("tx", 1.0),
            _max_along("ty", 1.0),
            _max_along("tz", 1.0),
        )
        min_rot = Vector3(
            _max_along("rx", -1.0),
            _max_along("ry", -1.0),
            _max_along("rz", -1.0),
        )
        max_rot = Vector3(
            _max_along("rx", 1.0),
            _max_along("ry", 1.0),
            _max_along("rz", 1.0),
        )

        return (
            Pose(translation=min_trans, rotation=min_rot),
            Pose(translation=max_trans, rotation=max_rot),
        )
