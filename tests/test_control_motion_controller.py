# test_control_motion_controller.py
# ==================================
# Tester for MotionController-klassen.
#
# MotionController er hovedorkestratorene som binder alt sammen:
# IMU-sensorer -> IMU-fusjon -> PID-kontroll -> IK -> sikkerhet -> servoer.
# Den kjorer kontrollsloyfen og haandterer oppstart/stopp/nodstopp.
#
# GUI-relevans:
#   MotionController er det sentrale grensesnittet mellom GUI og plattform:
#   - GUI kaller set_target_pose() nar brukeren endrer mal-pose
#   - GUI poller get_current_pose() for naavaerende tilstand
#   - GUI poller get_servo_angles() for servovisning
#   - GUI kaller start()/stop()/emergency_stop() for kontroll
#   - GUI sjekker is_running() for statusvisning

from unittest.mock import MagicMock, patch

import pytest

from stewart_platform.config.platform_config import PlatformConfig
from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.geometry.pose import Pose
from stewart_platform.control.motion_controller import MotionController


@pytest.fixture
def controller(default_platform_config):
    """MotionController med standard konfigurasjon (ikke initialisert)."""
    return MotionController(default_platform_config)


class TestMotionControllerOpprettelse:
    """Tester for opprettelse av MotionController."""

    def test_opprettelse(self, controller):
        """Sjekk at MotionController kan opprettes fra konfigurasjon."""
        assert controller is not None

    def test_starter_ikke_kjorende(self, controller):
        """Sjekk at kontrolleren ikke kjorer ved opprettelse."""
        assert controller.is_running() is False

    def test_starter_med_hjemmepose(self, controller):
        """Sjekk at mal-pose og naavaerende pose er hjemmepose ved oppstart."""
        current = controller.get_current_pose()
        assert current.translation.x == 0.0
        assert current.translation.y == 0.0
        assert current.translation.z == 0.0

    def test_lagrer_konfigurasjon(self, controller, default_platform_config):
        """Sjekk at konfigurasjonen lagres for senere bruk."""
        assert controller._config is default_platform_config

    def test_loop_rate_fra_config(self, controller):
        """Sjekk at kontrollsloyfe-frekvensen leses fra konfigurasjon."""
        assert controller._loop_rate_hz == 50.0

    def test_komponenter_er_none_for_init(self, controller):
        """Sjekk at maskinvarekomponenter er None for initialize() kalles.

        Ingen maskinvare skal initialiseres i konstruktoren.
        """
        assert controller._servo_array is None
        assert controller._base_imu is None
        assert controller._ik_solver is None
        assert controller._safety_monitor is None


class TestMotionControllerGetters:
    """Tester for getter-metoder som GUI-en bruker.

    Disse metodene gir GUI-en tilgang til sanntidsdata
    uten a endre plattformens tilstand.
    """

    def test_get_current_pose_returnerer_pose(self, controller):
        """Sjekk at get_current_pose() returnerer en Pose-instans."""
        pose = controller.get_current_pose()
        assert isinstance(pose, Pose)

    def test_get_servo_angles_uten_init(self, controller):
        """Sjekk at get_servo_angles() returnerer tom liste for initialisering.

        GUI-en skal haandtere at servo-data ikke er tilgjengelig enna.
        """
        angles = controller.get_servo_angles()
        assert angles == []

    def test_is_running_returnerer_bool(self, controller):
        """Sjekk at is_running() returnerer en boolsk verdi."""
        assert isinstance(controller.is_running(), bool)


class TestMotionControllerMetoder:
    """Tester for at nodvendige metoder eksisterer.

    Disse metodene ma vaere implementert for at GUI-en
    kan styre plattformen.
    """

    def test_initialize_eksisterer(self, controller):
        """Sjekk at initialize() eksisterer for maskinvareoppstart."""
        assert hasattr(controller, 'initialize')
        assert callable(controller.initialize)

    def test_set_target_pose_eksisterer(self, controller):
        """Sjekk at set_target_pose() eksisterer for GUI-styrt posisjonering."""
        assert hasattr(controller, 'set_target_pose')
        assert callable(controller.set_target_pose)

    def test_start_eksisterer(self, controller):
        """Sjekk at start() eksisterer for a starte kontrollsloyfen."""
        assert hasattr(controller, 'start')
        assert callable(controller.start)

    def test_stop_eksisterer(self, controller):
        """Sjekk at stop() eksisterer for kontrollert stopp."""
        assert hasattr(controller, 'stop')
        assert callable(controller.stop)

    def test_emergency_stop_eksisterer(self, controller):
        """Sjekk at emergency_stop() eksisterer for nodstopp.

        GUI-en skal ha en tydelig nodstopp-knapp.
        """
        assert hasattr(controller, 'emergency_stop')
        assert callable(controller.emergency_stop)

    def test_step_eksisterer(self, controller):
        """Sjekk at step() eksisterer for enkeltstegs-kjoring.

        Nyttig for debugging og testing via GUI.
        """
        assert hasattr(controller, 'step')
        assert callable(controller.step)

    def test_shutdown_eksisterer(self, controller):
        """Sjekk at shutdown() eksisterer for sikker avslutning."""
        assert hasattr(controller, 'shutdown')
        assert callable(controller.shutdown)

    def test_home_eksisterer(self, controller):
        """Sjekk at home() eksisterer for a ga til hjemmeposisjon."""
        assert hasattr(controller, 'home')
        assert callable(controller.home)


class TestMotionControllerHome:
    """Tester for home()-metoden."""

    def test_home_delegerer_til_servo_array(self, controller):
        """Sjekk at home() kaller ServoArray.go_home()."""
        mock_servo_array = MagicMock()
        controller._servo_array = mock_servo_array
        controller.home()
        mock_servo_array.go_home.assert_called_once()

    def test_home_resetter_target_pose(self, controller):
        """Sjekk at home() setter target_pose tilbake til hjemmepose."""
        controller._target_pose = Pose(
            translation=Vector3(10.0, 20.0, 30.0),
            rotation=Vector3(5.0, 10.0, 15.0),
        )
        mock_servo_array = MagicMock()
        controller._servo_array = mock_servo_array
        controller.home()
        assert controller.target_pose.translation.x == 0.0
        assert controller.target_pose.translation.y == 0.0
        assert controller.target_pose.translation.z == 0.0

    def test_home_uten_init_gjor_ingenting(self, controller):
        """Sjekk at home() ikke krasjer naar servo_array er None."""
        controller.home()  # Skal ikke kaste exception


class TestMotionControllerSetTargetPoseBool:
    """Tester for set_target_pose() som returnerer bool."""

    def test_gyldig_pose_returnerer_true(self, controller):
        """Sjekk at gyldig pose aksepteres og returnerer True."""
        pose = Pose(translation=Vector3(1.0, 1.0, 1.0))
        result = controller.set_target_pose(pose)
        assert result is True
        assert controller.target_pose.translation.x == 1.0

    def test_ugyldig_pose_returnerer_false(self, controller):
        """Sjekk at ugyldig pose avvises og returnerer False.

        Posen er utenfor sikkerhetsgrensene (max_translation_mm=50).
        """
        from stewart_platform.config.platform_config import SafetyConfig, ServoConfig
        from stewart_platform.safety.safety_monitor import SafetyMonitor

        monitor = SafetyMonitor(SafetyConfig(max_translation_mm=10.0), [ServoConfig()] * 6)
        controller._safety_monitor = monitor

        pose = Pose(translation=Vector3(100.0, 100.0, 100.0))
        result = controller.set_target_pose(pose)
        assert result is False

    def test_ugyldig_pose_endrer_ikke_target(self, controller):
        """Sjekk at avvist pose ikke endrer eksisterende target."""
        from stewart_platform.config.platform_config import SafetyConfig, ServoConfig
        from stewart_platform.safety.safety_monitor import SafetyMonitor

        monitor = SafetyMonitor(SafetyConfig(max_translation_mm=10.0), [ServoConfig()] * 6)
        controller._safety_monitor = monitor

        original = controller.target_pose
        pose = Pose(translation=Vector3(100.0, 100.0, 100.0))
        controller.set_target_pose(pose)
        assert controller.target_pose.translation.x == original.translation.x
