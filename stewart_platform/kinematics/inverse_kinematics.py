# inverse_kinematics.py
# =====================
# Invers kinematikk-solver for Stewart-plattformen.
# Gitt en ønsket 6-DOF pose (translasjon + rotasjon), beregner
# denne klassen de 6 servovinklene som trengs for å oppnå posen.
# Dette er det matematiske hjertet i styringssystemet.

from __future__ import annotations

import math
from typing import List, Optional, Tuple

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

    Klemming: Hvis en pose ligger marginalt utenfor det fysisk
    oppnåelige (sin-overskridelse eller vinkel utenfor mekanisk
    grense), kaster ikke solve() lenger. I stedet "fryses"
    løsningen til siste gyldige sett vinkler — det betyr i praksis
    at servoene ikke beveger seg lengre i den retningen som er
    umulig. Diagnostikk er tilgjengelig via last_solve_clamped /
    last_clamped_mask. For streng oppnåelighetstest (workspace-
    binærsøk osv.), bruk is_pose_reachable_exact().
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
        # Siste fullt gyldige vinkler — brukes som "freeze"-fallback
        # når ny pose er marginalt utenfor workspace.
        self._last_valid_angles: Optional[List[float]] = None
        self._last_solve_clamped: bool = False
        self._last_clamped_mask: List[bool] = [False] * 6

    @property
    def last_solve_clamped(self) -> bool:
        """True hvis siste solve() måtte klemme eller fryse."""
        return self._last_solve_clamped

    @property
    def last_clamped_mask(self) -> List[bool]:
        """Per-servo-flagg fra siste solve(): True for servoer der
        sin-overskridelse eller vinkelgrense måtte klemmes."""
        return list(self._last_clamped_mask)

    def solve(self, pose: Pose) -> List[float]:
        """Løs invers kinematikk for en gitt pose.

        Beregner de 6 servovinklene som plasserer toppplaten
        i den ønskede posisjonen og orienteringen. Hvis posen
        ligger marginalt utenfor workspace blir resultatet
        "frosset" på siste gyldige løsning (eller klemt til
        grenseverdier ved aller første kall) — det vil si at
        servoene ikke beveger seg videre i en umulig retning.
        Bruk last_solve_clamped/last_clamped_mask for å se om
        det skjedde.

        Args:
            pose: Ønsket 6-DOF pose for toppplaten.

        Returns:
            Liste med 6 servovinkler i grader.

        Raises:
            ValueError: Kun ved degenerert geometri (R < 1e-10 i
                        servoplanet) — en ekte beregningsumulighet,
                        ikke bare en pose utenfor workspace.
        """
        leg_vectors = self._geometry.get_leg_vectors(pose)
        angles: List[float] = []
        clamped_mask: List[bool] = [False] * 6

        for i, leg_vec in enumerate(leg_vectors):
            angle, sin_clamped = self._leg_length_to_servo_angle(leg_vec, i)
            sc = self._servo_configs[i]
            angle_clamped = False
            if angle < sc.min_angle_deg:
                angle = sc.min_angle_deg
                angle_clamped = True
            elif angle > sc.max_angle_deg:
                angle = sc.max_angle_deg
                angle_clamped = True
            clamped_mask[i] = sin_clamped or angle_clamped
            angles.append(angle)

        self._last_clamped_mask = clamped_mask
        self._last_solve_clamped = any(clamped_mask)

        if self._last_solve_clamped:
            # "Freeze" på siste gyldige løsning slik at servoene ikke
            # presses lengre i en umulig retning. Ved aller første
            # kall finnes ingen forrige løsning — bruk de klemte
            # vinklene som beste tilnærming.
            if self._last_valid_angles is not None:
                return list(self._last_valid_angles)
            return list(angles)

        self._last_valid_angles = list(angles)
        return angles

    def _leg_length_to_servo_angle(
        self,
        leg_vector: Vector3,
        servo_index: int,
    ) -> Tuple[float, bool]:
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
            Tuple (vinkel_deg, sin_klemt). sin_klemt er True hvis
            sin-verdien måtte klemmes til [-1, 1] for at asin()
            skulle være definert (dvs. posen er marginalt utenfor
            workspace fra denne servoens synsvinkel).

        Raises:
            ValueError: Når leg-vektorens komponent i servoplanet er
                        null (R < 1e-10) — en ekte degenerert
                        geometrisk situasjon.
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
        # Klem alltid sin_val til [-1, 1] slik at asin() er definert.
        # Hvis klemming skjer markerer vi det med sin_clamped=True;
        # solve() bruker dette til å avgjøre om hele løsningen er
        # "klemt" og dermed bør fryses i stedet for sendt videre.
        sin_clamped = sin_val < -1.0 or sin_val > 1.0
        sin_val = max(-1.0, min(1.0, sin_val))

        delta = math.atan2(L_z, L_r)
        alpha = delta + math.asin(sin_val)

        # Returner ren geometrisk vinkel; rotasjonsretning og offset
        # håndteres av Servo.angle_to_pulse_us slik at samme verdi
        # gir samme fysisk pose for både direction=+1 og direction=-1.
        return math.degrees(alpha), sin_clamped

    def is_pose_reachable(self, pose: Pose) -> bool:
        """Sjekk om en pose er fysisk oppnåelig.

        Etter at solve() ble klemmebasert returnerer denne metoden
        nå det samme som is_pose_reachable_exact() — en streng
        test av om alle 6 beinlengder og servovinkler er innenfor
        grensene uten klemming. Dette bevarer eksisterende kontrakt
        for kallere som bruker metoden til workspace-visualisering.

        Args:
            pose: Posen som skal sjekkes.

        Returns:
            True hvis posen kan oppnås uten klemming.
        """
        return self.is_pose_reachable_exact(pose)

    def is_pose_reachable_exact(self, pose: Pose) -> bool:
        """Streng oppnåelighetstest uten klemming.

        Brukes av kallere som må
        vite om en pose er *fysisk* oppnåelig (ikke bare hvilket
        klemt resultat solve() ville returnere). Returnerer False
        både ved sin-overskridelse i noen servo og ved vinkel
        utenfor [min_angle_deg, max_angle_deg].

        Args:
            pose: Posen som skal sjekkes.

        Returns:
            True hvis alle 6 servoer kan løses uten klemming.
        """
        try:
            leg_vectors = self._geometry.get_leg_vectors(pose)
        except ValueError:
            return False
        for i, leg_vec in enumerate(leg_vectors):
            try:
                angle, sin_clamped = self._leg_length_to_servo_angle(leg_vec, i)
            except ValueError:
                return False
            if sin_clamped:
                return False
            sc = self._servo_configs[i]
            if not (sc.min_angle_deg <= angle <= sc.max_angle_deg):
                return False
        return True

