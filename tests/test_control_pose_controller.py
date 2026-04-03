# test_control_pose_controller.py
# ================================
# Tester for PoseController-klassen.
#
# PoseController bruker 6 PID-regulatorer (en per frihetsgrad)
# for a minimere avviket mellom mal-pose og naavaerende pose.
# Utgangen er en korrigert pose som sendes til IK-solveren.
#
# GUI-relevans:
#   GUI-en setter mal-pose via sliders. PoseController beregner
#   korreksjonen. GUI-en kan vise avviket per akse og PID-utgangen
#   for a hjelpe med tuning.

import pytest

from stewart_platform.config.platform_config import PIDGains
from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.geometry.pose import Pose
from stewart_platform.control.pose_controller import PoseController


@pytest.fixture
def pose_ctrl():
    """Standard PoseController med P-regulator for alle akser."""
    return PoseController(PIDGains(kp=1.0, ki=0.0, kd=0.0))


class TestPoseControllerOpprettelse:
    """Tester for opprettelse av PoseController."""

    def test_opprettelse(self, pose_ctrl):
        """Sjekk at PoseController opprettes med 6 PID-regulatorer."""
        assert len(pose_ctrl._controllers) == 6

    def test_alle_regulatorer_er_pid(self, pose_ctrl):
        """Sjekk at alle 6 regulatorer er PIDController-instanser."""
        from stewart_platform.control.pid_controller import PIDController
        for ctrl in pose_ctrl._controllers:
            assert isinstance(ctrl, PIDController)


class TestPoseControllerUpdate:
    """Tester for update-metoden som beregner pose-korreksjon."""

    def test_ingen_avvik_gir_null_korreksjon(self, pose_ctrl):
        """Sjekk at lik mal-pose og naavaerende pose gir null korreksjon.

        Nar plattformen allerede er der den skal vaere, skal
        korreksjonen vaere (tilnaermet) null for alle akser.
        """
        target = Pose(
            translation=Vector3(10.0, 20.0, 30.0),
            rotation=Vector3(5.0, 10.0, 15.0),
        )
        current = Pose(
            translation=Vector3(10.0, 20.0, 30.0),
            rotation=Vector3(5.0, 10.0, 15.0),
        )
        result = pose_ctrl.update(target, current, dt=0.02)
        assert isinstance(result, Pose)
        assert result.translation.x == pytest.approx(0.0, abs=1e-6)
        assert result.translation.y == pytest.approx(0.0, abs=1e-6)
        assert result.translation.z == pytest.approx(0.0, abs=1e-6)
        assert result.rotation.x == pytest.approx(0.0, abs=1e-6)
        assert result.rotation.y == pytest.approx(0.0, abs=1e-6)
        assert result.rotation.z == pytest.approx(0.0, abs=1e-6)

    def test_avvik_gir_korreksjon(self, pose_ctrl):
        """Sjekk at avvik mellom mal og naavaerende pose gir en korreksjon.

        Nar plattformen er lavere enn malet, skal Z-korreksjonen
        vaere positiv (driv oppover).
        """
        target = Pose(translation=Vector3(0.0, 0.0, 10.0))
        current = Pose(translation=Vector3(0.0, 0.0, 0.0))
        result = pose_ctrl.update(target, current, dt=0.02)
        assert result.translation.z > 0.0

    def test_returnerer_pose(self, pose_ctrl):
        """Sjekk at update() alltid returnerer en Pose-instans."""
        result = pose_ctrl.update(Pose(), Pose(), dt=0.02)
        assert isinstance(result, Pose)


class TestPoseControllerReset:
    """Tester for reset av PoseController."""

    def test_reset_alle_regulatorer(self, pose_ctrl):
        """Sjekk at reset() nullstiller alle 6 PID-regulatorer.

        Viktig etter nodstopp for ren oppstart.
        """
        # Kjor noen oppdateringer for a bygge opp intern tilstand
        target = Pose(translation=Vector3(10.0, 10.0, 10.0))
        current = Pose()
        for _ in range(10):
            pose_ctrl.update(target, current, dt=0.02)

        pose_ctrl.reset()
        for ctrl in pose_ctrl._controllers:
            assert ctrl._integral == 0.0
            assert ctrl._previous_error == 0.0


class TestPoseControllerSetGains:
    """Tester for sanntidsjustering av PID-parametere."""

    def test_set_gains_oppdaterer_alle(self, pose_ctrl):
        """Sjekk at set_gains() oppdaterer alle 6 regulatorer.

        GUI-en bruker dette for global PID-tuning.
        """
        nye_gains = PIDGains(kp=5.0, ki=1.0, kd=0.5)
        pose_ctrl.set_gains(nye_gains)
        for ctrl in pose_ctrl._controllers:
            assert ctrl._gains.kp == 5.0
            assert ctrl._gains.ki == 1.0
            assert ctrl._gains.kd == 0.5
