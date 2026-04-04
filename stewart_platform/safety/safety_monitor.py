# safety_monitor.py
# =================
# Sikkerhetsovervåker for Stewart-plattformen.
# Sitter mellom kontrolleren og servoene, og validerer alle
# kommandoer mot sikkerhetsgrenser før de utføres.
# Kan utløse nødstopp ved kritiske feil.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from ..config.platform_config import SafetyConfig, ServoConfig
from ..geometry.pose import Pose
from ..geometry.vector3 import Vector3


class SafetySeverity(Enum):
    """Alvorlighetsgrad for sikkerhetsbrudd.

    Brukes for å klassifisere sikkerhetsbrudd slik at systemet
    kan reagere ulikt på advarsler vs. kritiske feil.
    """
    WARNING = "warning"    # Nær grense, men fortsatt innenfor. Logg advarsel.
    ERROR = "error"        # Grense overskredet. Avvis kommando.
    CRITICAL = "critical"  # Farlig tilstand. Utløs nødstopp umiddelbart.


@dataclass
class SafetyCheckResult:
    """Resultat fra en sikkerhetskontroll.

    Inneholder informasjon om hvorvidt en handling er trygg,
    og detaljerte meldinger om eventuelle brudd.
    """

    # True hvis alle sikkerhetssjekker bestod.
    is_safe: bool = True

    # Liste med beskrivelser av sikkerhetsbrudd.
    violations: List[str] = field(default_factory=list)

    # Høyeste alvorlighetsgrad blant eventuelle brudd.
    severity: SafetySeverity = SafetySeverity.WARNING


class SafetyMonitor:
    """Sikkerhetsovervåker for Stewart-plattformen.

    Validerer alle bevegelseskommandoer mot konfigurerbare
    sikkerhetsgrenser. Sjekker:
    - Pose-grenser (translasjon og rotasjon).
    - Servovinkler (innenfor mekaniske grenser med margin).
    - Hastigheter (lineær og vinkel).
    - IMU-data (akselerasjon innenfor fornuftige verdier).

    Hvis en kritisk grense overskrides, utløses nødstopp
    som frikoblet alle servoer umiddelbart.

    SafetyMonitor er uavhengig av MotionController slik at
    den kan testes og konfigureres separat.
    """

    def __init__(
        self,
        config: SafetyConfig,
        servo_configs: List[ServoConfig],
    ) -> None:
        """Opprett en sikkerhetsovervåker.

        Args:
            config: Sikkerhetsgrenser (maks translasjon, rotasjon, osv.).
            servo_configs: Servokonfigurasjoner for grensekontroll.
        """
        self._config = config
        self._servo_configs = servo_configs
        self._last_pose = Pose.home()
        self._last_time = 0.0
        self._emergency_stopped = False

    def validate_pose(self, pose: Pose) -> bool:
        """Sjekk om en pose er innenfor tillatte grenser.

        Sjekker at translasjon og rotasjon ikke overskrider
        max_translation_mm og max_rotation_deg.

        Args:
            pose: Posen som skal valideres.

        Returns:
            True hvis posen er innenfor grensene.
        """
        return pose.is_within_bounds(
            self._config.max_translation_mm,
            self._config.max_rotation_deg,
        )

    def validate_servo_angles(self, angles: List[float]) -> bool:
        """Sjekk om alle servovinkler er innenfor mekaniske grenser.

        Tar hensyn til servo_angle_margin_deg for å holde en
        sikkerhetsmargin til de absolutte grensene.

        Args:
            angles: Liste med 6 servovinkler i grader.

        Returns:
            True hvis alle vinkler er innenfor grensene med margin.
        """
        margin = self._config.servo_angle_margin_deg
        for i, angle in enumerate(angles):
            sc = self._servo_configs[i]
            if angle < sc.min_angle_deg + margin or angle > sc.max_angle_deg - margin:
                return False
        return True

    def validate_velocity(
        self,
        current: Pose,
        previous: Pose,
        dt: float,
    ) -> bool:
        """Sjekk at bevegelseshastigheten er innenfor tillatte grenser.

        Beregner lineær og vinkelhastighet mellom to påfølgende
        poser, og sammenligner med max_velocity_mm_per_s og
        max_angular_velocity_deg_per_s.

        Args:
            current: Nåværende pose.
            previous: Forrige pose.
            dt: Tid mellom de to posene i sekunder.

        Returns:
            True hvis hastigheten er innenfor grensene.
        """
        if dt <= 0:
            return True

        delta_trans = current.translation - previous.translation
        linear_speed = delta_trans.magnitude() / dt
        if linear_speed > self._config.max_velocity_mm_per_s:
            return False

        delta_rot = current.rotation - previous.rotation
        angular_speed = delta_rot.magnitude() / dt
        if angular_speed > self._config.max_angular_velocity_deg_per_s:
            return False

        return True

    def validate_imu_readings(self, accel: Vector3) -> bool:
        """Sjekk at IMU-akselerasjonsdata er innenfor fornuftige verdier.

        Ekstremt høye akselerasjonsverdier kan indikere sensorfeil,
        kollisjon eller annen uønsket tilstand.

        Args:
            accel: Akselerasjonsdata i m/s² (X, Y, Z).

        Returns:
            True hvis akselerasjonen er under imu_fault_threshold_g.
        """
        # Konverter terskel fra g til m/s² (1g ≈ 9.81 m/s²)
        threshold_ms2 = self._config.imu_fault_threshold_g * 9.81
        return accel.magnitude() <= threshold_ms2

    def trigger_emergency_stop(self) -> None:
        """Utløs nødstopp.

        Setter nødstopp-flagget. MotionController sjekker dette
        flagget og frikobler alle servoer umiddelbart.
        """
        self._emergency_stopped = True

    def reset_emergency_stop(self) -> None:
        """Tilbakestill nødstopp-flagget.

        Tillater systemet å gjenoppta normal drift etter at
        årsaken til nødstoppen er utbedret.
        """
        self._emergency_stopped = False

    def is_emergency_stopped(self) -> bool:
        """Sjekk om nødstopp er aktiv.

        Returns:
            True hvis nødstopp er utløst.
        """
        return self._emergency_stopped

    def check_all(
        self,
        pose: Pose,
        angles: List[float],
        accel: Vector3,
        dt: float,
    ) -> SafetyCheckResult:
        """Utfør alle sikkerhetskontroller samlet.

        Kjører alle validerings-metoder og returnerer et samlet
        resultat med eventuelle brudd og alvorlighetsgrad.
        Hvis noen sjekk feiler med CRITICAL alvorlighet, utløses
        nødstopp automatisk.

        Args:
            pose: Posen som skal valideres.
            angles: Servovinkler som skal valideres.
            accel: IMU-akselerasjonsdata.
            dt: Tid siden forrige sjekk i sekunder.

        Returns:
            SafetyCheckResult med status og eventuelle brudd.
        """
        violations: List[str] = []

        if not self.validate_pose(pose):
            violations.append("Pose utenfor tillatte grenser.")

        if not self.validate_servo_angles(angles):
            violations.append("Servovinkler utenfor tillatte grenser.")

        if not self.validate_imu_readings(accel):
            violations.append("IMU-akselerasjon over feilterskel.")

        if not self.validate_velocity(pose, self._last_pose, dt):
            violations.append("Hastighet over tillatt grense.")

        self._last_pose = pose

        if not violations:
            return SafetyCheckResult(is_safe=True)

        # Bestem alvorlighetsgrad basert på antall brudd
        if len(violations) >= 3:
            severity = SafetySeverity.CRITICAL
        elif len(violations) >= 2:
            severity = SafetySeverity.ERROR
        else:
            severity = SafetySeverity.ERROR

        if severity == SafetySeverity.CRITICAL:
            self.trigger_emergency_stop()

        return SafetyCheckResult(
            is_safe=False,
            violations=violations,
            severity=severity,
        )
