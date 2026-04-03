# test_safety_safety_monitor.py
# ==============================
# Tester for SafetyMonitor, SafetyCheckResult og SafetySeverity.
#
# SafetyMonitor er sikkerhetslaget mellom kontrolleren og servoene.
# Den validerer alle kommandoer mot konfigurerbare sikkerhetsgrenser
# for de utfores, og kan utlose nodstopp ved kritiske feil.
#
# GUI-relevans:
#   GUI-en skal vise sikkerhetsstatus i sanntid:
#   - Gront: alt OK
#   - Gult: advarsel (naer grense)
#   - Rodt: feil/kritisk (grense overskredet eller nodstopp)
#   GUI-en har ogsa en nodstopp-knapp som kaller trigger_emergency_stop()
#   og en tilbakestill-knapp for reset_emergency_stop().

import pytest

from stewart_platform.config.platform_config import SafetyConfig, ServoConfig
from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.geometry.pose import Pose
from stewart_platform.safety.safety_monitor import (
    SafetyMonitor,
    SafetyCheckResult,
    SafetySeverity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def monitor():
    """Standard SafetyMonitor med konservative grenser."""
    config = SafetyConfig()
    servo_configs = [
        ServoConfig(channel=i, mounting_angle_deg=i * 60.0)
        for i in range(6)
    ]
    return SafetyMonitor(config, servo_configs)


@pytest.fixture
def stram_monitor():
    """SafetyMonitor med svart stramme grenser for testing."""
    config = SafetyConfig(
        max_translation_mm=10.0,
        max_rotation_deg=5.0,
        max_velocity_mm_per_s=20.0,
        max_angular_velocity_deg_per_s=10.0,
        servo_angle_margin_deg=10.0,
        imu_fault_threshold_g=2.0,
    )
    servo_configs = [
        ServoConfig(channel=i, mounting_angle_deg=i * 60.0)
        for i in range(6)
    ]
    return SafetyMonitor(config, servo_configs)


# ===========================================================================
# SafetySeverity enum
# ===========================================================================

class TestSafetySeverity:
    """Tester for SafetySeverity-enumet."""

    def test_warning_finnes(self):
        """Sjekk at WARNING-nivaet finnes."""
        assert SafetySeverity.WARNING is not None

    def test_error_finnes(self):
        """Sjekk at ERROR-nivaet finnes."""
        assert SafetySeverity.ERROR is not None

    def test_critical_finnes(self):
        """Sjekk at CRITICAL-nivaet finnes (utloser nodstopp)."""
        assert SafetySeverity.CRITICAL is not None


# ===========================================================================
# SafetyCheckResult dataklasse
# ===========================================================================

class TestSafetyCheckResult:
    """Tester for SafetyCheckResult dataklasse."""

    def test_standardverdier(self):
        """Sjekk at standardresultatet er 'trygt' (ingen brudd)."""
        result = SafetyCheckResult()
        assert result.is_safe is True
        assert result.violations == []
        assert result.severity == SafetySeverity.WARNING

    def test_egendefinert_resultat(self):
        """Sjekk at alle felter kan settes."""
        result = SafetyCheckResult(
            is_safe=False,
            violations=["Pose utenfor grense", "Servo 3 over maks"],
            severity=SafetySeverity.ERROR,
        )
        assert result.is_safe is False
        assert len(result.violations) == 2
        assert result.severity == SafetySeverity.ERROR


# ===========================================================================
# SafetyMonitor — Opprettelse og nodstopp
# ===========================================================================

class TestSafetyMonitorOpprettelse:
    """Tester for opprettelse av SafetyMonitor."""

    def test_opprettelse(self, monitor):
        """Sjekk at SafetyMonitor kan opprettes med konfigurasjon."""
        assert monitor is not None

    def test_starter_uten_nodstopp(self, monitor):
        """Sjekk at nodstopp ikke er aktiv ved oppstart."""
        assert monitor.is_emergency_stopped() is False

    def test_lagrer_config(self, monitor):
        """Sjekk at sikkerhetskonfigurasjonen lagres."""
        assert monitor._config.max_translation_mm == 50.0

    def test_lagrer_servo_configs(self, monitor):
        """Sjekk at servokonfigurasjonene lagres for grensekontroll."""
        assert len(monitor._servo_configs) == 6


# ===========================================================================
# SafetyMonitor — Nodstopp
# ===========================================================================

class TestNodstopp:
    """Tester for nodstopp-funksjonalitet.

    GUI-en har en tydelig nodstopp-knapp som kaller
    trigger_emergency_stop(). En separat knapp for
    reset_emergency_stop() lar brukeren gjenoppta drift.
    """

    def test_trigger_emergency_stop(self, monitor):
        """Sjekk at trigger_emergency_stop() setter nodstopp-flagget."""
        monitor.trigger_emergency_stop()
        assert monitor.is_emergency_stopped() is True

    def test_reset_emergency_stop(self, monitor):
        """Sjekk at reset_emergency_stop() fjerner nodstopp-flagget."""
        monitor.trigger_emergency_stop()
        assert monitor.is_emergency_stopped() is True
        monitor.reset_emergency_stop()
        assert monitor.is_emergency_stopped() is False

    def test_dobbel_trigger_er_ok(self, monitor):
        """Sjekk at nodstopp kan utloses flere ganger uten feil."""
        monitor.trigger_emergency_stop()
        monitor.trigger_emergency_stop()
        assert monitor.is_emergency_stopped() is True


# ===========================================================================
# SafetyMonitor — Pose-validering
# ===========================================================================

class TestPoseValidering:
    """Tester for validering av pose mot sikkerhetsgrenser.

    GUI-en bruker dette for a vise nar brukeren naermer seg
    grensene for tillatt bevegelse.
    """

    def test_hjemmepose_er_trygg(self, monitor):
        """Sjekk at hjemmeposen (nullpose) alltid er innenfor grensene."""
        assert monitor.validate_pose(Pose.home()) is True

    def test_liten_translasjon_er_trygg(self, monitor):
        """Sjekk at sma bevegelser innenfor grensene godkjennes."""
        pose = Pose(translation=Vector3(10.0, 10.0, 10.0))
        assert monitor.validate_pose(pose) is True

    def test_for_stor_translasjon_avvises(self, monitor):
        """Sjekk at translasjon over max_translation_mm (50) avvises."""
        pose = Pose(translation=Vector3(60.0, 0.0, 0.0))
        assert monitor.validate_pose(pose) is False

    def test_for_stor_rotasjon_avvises(self, monitor):
        """Sjekk at rotasjon over max_rotation_deg (30) avvises."""
        pose = Pose(rotation=Vector3(35.0, 0.0, 0.0))
        assert monitor.validate_pose(pose) is False

    def test_liten_rotasjon_er_trygg(self, monitor):
        """Sjekk at sma rotasjoner innenfor grensene godkjennes."""
        pose = Pose(rotation=Vector3(10.0, 10.0, 10.0))
        assert monitor.validate_pose(pose) is True

    def test_stram_monitor_avviser_moderat_pose(self, stram_monitor):
        """Sjekk at stramme grenser (10mm) avviser moderate poser."""
        pose = Pose(translation=Vector3(15.0, 0.0, 0.0))
        assert stram_monitor.validate_pose(pose) is False


# ===========================================================================
# SafetyMonitor — Servovinkel-validering
# ===========================================================================

class TestServoVinkelValidering:
    """Tester for validering av servovinkler.

    Tar hensyn til servo_angle_margin_deg (5 grader) for a
    holde en sikkerhetsmargin til de absolutte mekaniske grensene.
    """

    def test_midtvinkler_er_trygge(self, monitor):
        """Sjekk at hjemmevinkler (90 grader) er trygge for alle servoer."""
        vinkler = [90.0] * 6
        assert monitor.validate_servo_angles(vinkler) is True

    def test_vinkler_innenfor_marginer(self, monitor):
        """Sjekk at vinkler innenfor margin godkjennes.

        Med margin=5: gyldige vinkler er 5.0 til 175.0 (for 0-180 servo).
        """
        vinkler = [10.0, 45.0, 90.0, 135.0, 170.0, 90.0]
        assert monitor.validate_servo_angles(vinkler) is True

    def test_vinkel_for_naer_minimum(self, monitor):
        """Sjekk at vinkel innenfor margin fra minimum avvises.

        Med min=0 og margin=5: vinkel 3.0 er for naer grensen.
        """
        vinkler = [3.0, 90.0, 90.0, 90.0, 90.0, 90.0]
        assert monitor.validate_servo_angles(vinkler) is False

    def test_vinkel_for_naer_maksimum(self, monitor):
        """Sjekk at vinkel innenfor margin fra maksimum avvises.

        Med max=180 og margin=5: vinkel 177.0 er for naer grensen.
        """
        vinkler = [90.0, 90.0, 90.0, 90.0, 90.0, 177.0]
        assert monitor.validate_servo_angles(vinkler) is False

    def test_vinkel_over_maksimum(self, monitor):
        """Sjekk at vinkel over mekanisk grense avvises."""
        vinkler = [90.0, 90.0, 90.0, 90.0, 90.0, 190.0]
        assert monitor.validate_servo_angles(vinkler) is False

    def test_vinkel_under_minimum(self, monitor):
        """Sjekk at vinkel under mekanisk grense avvises."""
        vinkler = [-5.0, 90.0, 90.0, 90.0, 90.0, 90.0]
        assert monitor.validate_servo_angles(vinkler) is False


# ===========================================================================
# SafetyMonitor — Hastighetsvalidering
# ===========================================================================

class TestHastighetsValidering:
    """Tester for validering av bevegelseshastighet.

    Hindrer at plattformen beveger seg for raskt,
    noe som kan skade mekanismen eller servoene.
    """

    def test_ingen_bevegelse_er_trygt(self, monitor):
        """Sjekk at ingen bevegelse (pose uendret) godkjennes."""
        pose = Pose(translation=Vector3(10.0, 10.0, 10.0))
        assert monitor.validate_velocity(pose, pose, dt=0.02) is True

    def test_sakte_bevegelse_er_trygt(self, monitor):
        """Sjekk at sakte bevegelse innenfor grensene godkjennes."""
        prev = Pose(translation=Vector3(0.0, 0.0, 0.0))
        curr = Pose(translation=Vector3(1.0, 0.0, 0.0))  # 1mm pa 0.02s = 50 mm/s
        assert monitor.validate_velocity(curr, prev, dt=0.02) is True

    def test_for_rask_bevegelse_avvises(self, monitor):
        """Sjekk at bevegelse over max_velocity_mm_per_s (100) avvises."""
        prev = Pose(translation=Vector3(0.0, 0.0, 0.0))
        curr = Pose(translation=Vector3(10.0, 0.0, 0.0))  # 10mm pa 0.02s = 500 mm/s
        assert monitor.validate_velocity(curr, prev, dt=0.02) is False


# ===========================================================================
# SafetyMonitor — IMU-validering
# ===========================================================================

class TestIMUValidering:
    """Tester for validering av IMU-akselerasjonsdata.

    Ekstremt hoye akselerasjoner kan tyde pa sensorfeil,
    kollisjon eller lossrivning.
    """

    def test_normal_gravitasjon_er_trygt(self, monitor):
        """Sjekk at normal gravitasjon (9.81 m/s^2 ~ 1g) godkjennes."""
        accel = Vector3(0.0, 0.0, 9.81)
        assert monitor.validate_imu_readings(accel) is True

    def test_for_hoy_akselerasjon_avvises(self, monitor):
        """Sjekk at akselerasjon over imu_fault_threshold_g (4g) avvises."""
        accel = Vector3(0.0, 0.0, 50.0)  # ~5g, over terskel
        assert monitor.validate_imu_readings(accel) is False


# ===========================================================================
# SafetyMonitor — Samlet sjekk (check_all)
# ===========================================================================

class TestCheckAll:
    """Tester for samlet sikkerhetssjekk.

    check_all() kjorer alle valideringer og returnerer et
    SafetyCheckResult med samlet status.
    """

    def test_alt_ok_gir_safe_result(self, monitor):
        """Sjekk at gyldige verdier gir is_safe=True."""
        result = monitor.check_all(
            pose=Pose.home(),
            angles=[90.0] * 6,
            accel=Vector3(0.0, 0.0, 9.81),
            dt=0.02,
        )
        assert isinstance(result, SafetyCheckResult)
        assert result.is_safe is True
        assert len(result.violations) == 0

    def test_ugyldig_pose_gir_unsafe_result(self, monitor):
        """Sjekk at ugyldig pose gir is_safe=False med forklaring."""
        result = monitor.check_all(
            pose=Pose(translation=Vector3(100.0, 0.0, 0.0)),
            angles=[90.0] * 6,
            accel=Vector3(0.0, 0.0, 9.81),
            dt=0.02,
        )
        assert result.is_safe is False
        assert len(result.violations) > 0

    def test_ugyldig_vinkel_gir_unsafe_result(self, monitor):
        """Sjekk at ugyldig servovinkel gir is_safe=False."""
        result = monitor.check_all(
            pose=Pose.home(),
            angles=[90.0, 90.0, 90.0, 90.0, 90.0, 200.0],
            accel=Vector3(0.0, 0.0, 9.81),
            dt=0.02,
        )
        assert result.is_safe is False

    def test_kritisk_feil_utloser_nodstopp(self, monitor):
        """Sjekk at en kritisk feil i check_all utloser nodstopp automatisk.

        Ekstreme verdier skal gi CRITICAL severity og aktivere nodstopp.
        """
        assert monitor.is_emergency_stopped() is False
        result = monitor.check_all(
            pose=Pose(translation=Vector3(500.0, 500.0, 500.0)),  # Ekstremt
            angles=[200.0] * 6,  # Alle over grense
            accel=Vector3(0.0, 0.0, 100.0),  # ~10g
            dt=0.02,
        )
        assert result.is_safe is False
        assert result.severity == SafetySeverity.CRITICAL
        assert monitor.is_emergency_stopped() is True
