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
        # Cache leddvinklene lokalt slik at IK ikke trenger å nå inn
        # i private felter på PlatformGeometry under hot path.
        self._base_joint_angles = geometry.get_base_joint_angles()
        self._servo_horn_length = geometry.get_servo_horn_length()
        self._rod_length = geometry.get_rod_length()

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
        # Servoens effektive retning = bunnleddets vinkel + monteringsoffset
        base_angle = self._base_joint_angles[servo_index]
        effective_mount_rad = math.radians(base_angle + sc.mounting_angle_deg)
        a = self._servo_horn_length
        s = self._rod_length

        # Dekomponér beinvektor i servoens lokale koordinater
        L_r = leg_vector.x * math.cos(effective_mount_rad) + leg_vector.y * math.sin(effective_mount_rad)
        L_z = leg_vector.z

        # Total beinlengde (3D)
        d_sq = leg_vector.x ** 2 + leg_vector.y ** 2 + leg_vector.z ** 2

        # Servovinkel α måles fra ned-posisjon (0°=ned, 90°=horisontal, 180°=opp).
        # Hornspiss relativ til bunnledd: (a·sin(α)·cos(m), a·sin(α)·sin(m), -a·cos(α))
        # Stang-constraint: L_r·sin(α) - L_z·cos(α) = M
        M = (d_sq + a ** 2 - s ** 2) / (2.0 * a)

        # Omskrevet: R·sin(α - δ) = M, der R = √(L_r² + L_z²), δ = atan2(L_z, L_r)
        R = math.sqrt(L_r ** 2 + L_z ** 2)
        if R < 1e-10:
            raise ValueError("Beinvektor har null lengde i servoplanet.")

        sin_val = M / R
        # Tolerer opptil ~10 % overskridelse av sin-grensen før vi
        # kaller posen uoppnåelig. Dette er bevisst romslig: for
        # standardgeometrien (a=25, s=150, base/topp-radius 100/75)
        # gir poser nær workspace-kanten sin-verdier opp mot 1.07,
        # og strammere terskel ville forkaste poser som faktisk er
        # mekanisk oppnåelige etter klemming. Klem deretter til
        # [-1, 1] før asin().
        if abs(sin_val) > 1.1:
            raise ValueError(
                f"Pose er ikke oppnåelig for servo {servo_index}: "
                f"sin = {sin_val:.4f}."
            )
        sin_val = max(-1.0, min(1.0, sin_val))

        delta = math.atan2(L_z, L_r)
        alpha = delta + math.asin(sin_val)

        # Returner ren geometrisk vinkel; rotasjonsretning og offset
        # håndteres av Servo.angle_to_pulse_us slik at samme verdi
        # gir samme fysisk pose for både direction=+1 og direction=-1.
        return math.degrees(alpha)

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
        # Binærsøk for maksimal translasjon/rotasjon langs hver akse.
        # axis_kind = "translation" | "rotation", component = "x"|"y"|"z".
        def _max_along(axis_kind: str, component: str, direction: float) -> float:
            lo, hi = 0.0, 200.0
            for _ in range(50):
                mid = (lo + hi) / 2.0
                t = {"x": 0.0, "y": 0.0, "z": 0.0}
                r = {"x": 0.0, "y": 0.0, "z": 0.0}
                if axis_kind == "translation":
                    t[component] = mid * direction
                else:
                    r[component] = mid * direction
                pose = Pose(
                    translation=Vector3(**t),
                    rotation=Vector3(**r),
                )
                if self.is_pose_reachable(pose):
                    lo = mid
                else:
                    hi = mid
            return lo * direction

        min_trans = Vector3(
            _max_along("translation", "x", -1.0),
            _max_along("translation", "y", -1.0),
            _max_along("translation", "z", -1.0),
        )
        max_trans = Vector3(
            _max_along("translation", "x", 1.0),
            _max_along("translation", "y", 1.0),
            _max_along("translation", "z", 1.0),
        )
        min_rot = Vector3(
            _max_along("rotation", "x", -1.0),
            _max_along("rotation", "y", -1.0),
            _max_along("rotation", "z", -1.0),
        )
        max_rot = Vector3(
            _max_along("rotation", "x", 1.0),
            _max_along("rotation", "y", 1.0),
            _max_along("rotation", "z", 1.0),
        )

        return (
            Pose(translation=min_trans, rotation=min_rot),
            Pose(translation=max_trans, rotation=max_rot),
        )
