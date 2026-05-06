# safety_monitor.py
# =================
# Sikkerhetsovervåker for Stewart-plattformen.
# Sitter mellom kontrolleren og servoene, og validerer alle
# kommandoer mot sikkerhetsgrenser før de utføres.
# Kan utløse nødstopp ved kritiske feil.

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

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
        self._e_stop_reason: Optional[str] = None
        self._check_history: deque[SafetyCheckResult] = deque(maxlen=100)

    def validate_pose(self, pose: Pose) -> bool:
        """Sjekk om rotasjonen er innenfor max_rotation_deg."""
        return pose.is_within_bounds(self._config.max_rotation_deg)

    def _servos_outside_margin(self, angles: List[float]) -> List[str]:
        """Returner detaljerte beskrivelser av servoer utenfor margin.

        Brukes av check_all for å bygge en informativ violation-melding
        som inkluderer servo-indeks, faktisk vinkel og grenseverdiene.
        """
        margin = self._config.servo_angle_margin_deg
        bad: List[str] = []
        for i, angle in enumerate(angles):
            sc = self._servo_configs[i]
            lo = sc.min_angle_deg + margin
            hi = sc.max_angle_deg - margin
            if angle < lo or angle > hi:
                bad.append(f"#{i}={angle:.1f}° [{lo:.0f}, {hi:.0f}]")
        return bad

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
        """Sjekk at vinkelhastigheten er innenfor max_angular_velocity_deg_per_s."""
        if dt <= 0:
            return True
        delta_rot = current.rotation - previous.rotation
        angular_speed = delta_rot.magnitude() / dt
        return angular_speed <= self._config.max_angular_velocity_deg_per_s

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

    def trigger_e_stop(self, reason: str = "") -> None:
        """Utløs nødstopp med valgfri årsak.

        Args:
            reason: Beskrivelse av hvorfor nødstoppen ble utløst.
        """
        self._emergency_stopped = True
        self._e_stop_reason = reason if reason else None

    @property
    def e_stop_reason(self) -> Optional[str]:
        """Hent årsaken til nødstoppen.

        Returns:
            Årsak-streng eller None hvis ingen årsak er satt.
        """
        return self._e_stop_reason

    def reset_latched_faults(self) -> bool:
        """Tilbakestill nødstopp og alle latchede feil.

        Returns:
            True hvis det var noe å tilbakestille, False ellers.
        """
        if not self._emergency_stopped:
            return False
        self._emergency_stopped = False
        self._e_stop_reason = None
        return True

    def is_e_stopped(self) -> bool:
        """Sjekk om nødstopp er aktiv.

        Returns:
            True hvis nødstopp er utløst.
        """
        return self._emergency_stopped

    def get_limits(self) -> SafetyConfig:
        """Hent nåværende sikkerhetsgrenser.

        Returns:
            SafetyConfig med aktive grenser.
        """
        return self._config

    def set_limits(self, config: SafetyConfig) -> None:
        """Oppdater sikkerhetsgrensene.

        Args:
            config: Nye sikkerhetsgrenser.
        """
        self._config = config

    def get_check_results(self) -> List[SafetyCheckResult]:
        """Hent historikk over sikkerhetssjekker (siste 100).

        Returns:
            Liste med SafetyCheckResult i kronologisk rekkefølge.
        """
        return list(self._check_history)

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
        # Bypass alle sjekker hvis monitoren er slått av i config.
        # Brukes under bringup/tuning der grensene må deaktiveres
        # midlertidig. _last_pose oppdateres fortsatt slik at
        # hastighetssjekken er korrekt når den slås på igjen.
        if not self._config.enabled:
            self._last_pose = pose
            result = SafetyCheckResult(is_safe=True)
            self._check_history.append(result)
            return result

        violations: List[str] = []

        if not self.validate_pose(pose):
            violations.append(
                f"Rotasjon utenfor grenser: |r|={pose.rotation.magnitude():.1f}° "
                f"(maks {self._config.max_rotation_deg})."
            )

        bad_servos = self._servos_outside_margin(angles)
        if bad_servos:
            violations.append("Servovinkler utenfor margin: " + ", ".join(bad_servos))

        if not self.validate_imu_readings(accel):
            violations.append(
                f"IMU-akselerasjon over feilterskel: |a|={accel.magnitude():.2f} m/s² "
                f"(terskel {self._config.imu_fault_threshold_g * 9.81:.2f})."
            )

        if dt > 0:
            delta_rot = pose.rotation - self._last_pose.rotation
            ang_speed = delta_rot.magnitude() / dt
            if ang_speed > self._config.max_angular_velocity_deg_per_s:
                violations.append(
                    f"Vinkelhastighet over grense: {ang_speed:.1f} °/s "
                    f"(maks {self._config.max_angular_velocity_deg_per_s})."
                )

        self._last_pose = pose

        if not violations:
            result = SafetyCheckResult(is_safe=True)
            self._check_history.append(result)
            return result

        # Bestem alvorlighetsgrad basert på antall brudd.
        # 1 brudd: WARNING (logges, kommando kan fortsatt utføres
        #   forsiktig av kaller om ønskelig).
        # 2 brudd: ERROR (avvis kommando).
        # 3+ brudd: CRITICAL (utløs nødstopp umiddelbart).
        if len(violations) >= 3:
            severity = SafetySeverity.CRITICAL
        elif len(violations) >= 2:
            severity = SafetySeverity.ERROR
        else:
            severity = SafetySeverity.WARNING

        result = SafetyCheckResult(
            is_safe=False,
            violations=violations,
            severity=severity,
        )
        self._check_history.append(result)
        return result
