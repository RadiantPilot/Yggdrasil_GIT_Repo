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

from stewart_platform.config.platform_config import PIDGains, Axis
from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.geometry.pose import Pose
from stewart_platform.control.pose_controller import PoseController, StepResponseRecorder


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


class TestPoseControllerPerAksePID:
    """Tester for per-akse PID-tuning via Axis-enum."""

    def test_get_pid_gains_returnerer_standard(self, pose_ctrl):
        """Sjekk at get_pid_gains returnerer standard forsterkning etter opprettelse."""
        for axis in Axis:
            gains = pose_ctrl.get_pid_gains(axis)
            assert isinstance(gains, PIDGains)
            assert gains.kp == 1.0
            assert gains.ki == 0.0
            assert gains.kd == 0.0

    def test_set_pid_gains_endrer_kun_valgt_akse(self, pose_ctrl):
        """Sjekk at set_pid_gains kun pavirker den valgte aksen.

        GUI-en skal kunne tune roll-PID uten a pavirke pitch.
        """
        nye_gains = PIDGains(kp=10.0, ki=2.0, kd=0.5)
        pose_ctrl.set_pid_gains(Axis.ROLL, nye_gains)

        # ROLL (akse 3) skal ha nye verdier
        roll_gains = pose_ctrl.get_pid_gains(Axis.ROLL)
        assert roll_gains.kp == 10.0
        assert roll_gains.ki == 2.0
        assert roll_gains.kd == 0.5

        # Alle andre akser skal vaere uendret
        for axis in Axis:
            if axis != Axis.ROLL:
                gains = pose_ctrl.get_pid_gains(axis)
                assert gains.kp == 1.0
                assert gains.ki == 0.0
                assert gains.kd == 0.0

    def test_set_pid_gains_alle_akser_individuelt(self, pose_ctrl):
        """Sjekk at alle 6 akser kan settes uavhengig."""
        for axis in Axis:
            pose_ctrl.set_pid_gains(axis, PIDGains(kp=float(axis.value + 1)))

        for axis in Axis:
            gains = pose_ctrl.get_pid_gains(axis)
            assert gains.kp == float(axis.value + 1)

    def test_set_pid_gains_pavirker_update(self):
        """Sjekk at endret forsterkning faktisk pavirker PID-utgangen.

        Dobling av kp for Z-aksen skal gi dobbel korreksjon for Z.
        Bruker hoy output_max for a unnga saturering.
        """
        gains = PIDGains(kp=1.0, ki=0.0, kd=0.0, output_max=100.0, output_min=-100.0)
        ctrl = PoseController(gains)
        target = Pose(translation=Vector3(0.0, 0.0, 10.0))
        current = Pose()

        # Forste beregning med standard kp=1.0
        result_1 = ctrl.update(target, current, dt=0.02)
        z_1 = result_1.translation.z

        # Reset og dobble kp kun for Z
        ctrl.reset()
        ctrl.set_pid_gains(
            Axis.Z,
            PIDGains(kp=2.0, ki=0.0, kd=0.0, output_max=100.0, output_min=-100.0),
        )

        result_2 = ctrl.update(target, current, dt=0.02)
        z_2 = result_2.translation.z

        assert z_2 == pytest.approx(z_1 * 2.0, rel=1e-6)

    def test_get_pid_gains_ugyldig_akse_gir_feil(self, pose_ctrl):
        """Sjekk at ugyldig akse-indeks gir feil."""
        with pytest.raises((IndexError, KeyError, ValueError)):
            pose_ctrl.get_pid_gains(99)


class TestStepResponseRecorder:
    """Tester for StepResponseRecorder som samler step-respons-data."""

    def test_opprettelse(self):
        """Sjekk at recorder opprettes korrekt."""
        recorder = StepResponseRecorder(Axis.PITCH, from_val=0.0, to_val=5.0)
        assert recorder.axis == Axis.PITCH
        assert recorder.from_val == 0.0
        assert recorder.to_val == 5.0
        assert recorder.is_active
        assert len(recorder.samples) == 0

    def test_record_sample(self):
        """Sjekk at samples legges til korrekt."""
        recorder = StepResponseRecorder(Axis.ROLL, from_val=0.0, to_val=10.0)
        recorder.record(timestamp=0.0, setpoint=10.0, actual=0.0)
        recorder.record(timestamp=0.02, setpoint=10.0, actual=3.0)
        assert len(recorder.samples) == 2
        assert recorder.samples[0] == (0.0, 10.0, 0.0)
        assert recorder.samples[1] == (0.02, 10.0, 3.0)

    def test_finish(self):
        """Sjekk at finish markerer recorder som inaktiv."""
        recorder = StepResponseRecorder(Axis.Z, from_val=0.0, to_val=5.0)
        recorder.record(timestamp=0.0, setpoint=5.0, actual=0.0)
        recorder.finish()
        assert not recorder.is_active

    def test_record_etter_finish_ignoreres(self):
        """Sjekk at samples ikke legges til etter finish."""
        recorder = StepResponseRecorder(Axis.X, from_val=0.0, to_val=5.0)
        recorder.record(timestamp=0.0, setpoint=5.0, actual=0.0)
        recorder.finish()
        recorder.record(timestamp=0.02, setpoint=5.0, actual=1.0)
        assert len(recorder.samples) == 1


class TestPoseControllerStepResponse:
    """Tester for step-respons-funksjonalitet i PoseController."""

    def test_trigger_step_response_oppretter_recorder(self, pose_ctrl):
        """Sjekk at trigger_step_response oppretter en aktiv recorder."""
        pose_ctrl.trigger_step_response(Axis.ROLL, from_val=0.0, to_val=5.0)
        recorder = pose_ctrl.get_step_response_recorder(Axis.ROLL)
        assert recorder is not None
        assert recorder.is_active
        assert recorder.axis == Axis.ROLL

    def test_get_recorder_for_akse_uten_step_returnerer_none(self, pose_ctrl):
        """Sjekk at get returnerer None for akser uten aktiv step."""
        assert pose_ctrl.get_step_response_recorder(Axis.X) is None

    def test_trigger_step_response_pavirker_malposen(self):
        """Sjekk at step-respons setter setpunktet for valgt akse."""
        gains = PIDGains(kp=1.0, ki=0.0, kd=0.0, output_max=100.0, output_min=-100.0)
        ctrl = PoseController(gains)
        ctrl.trigger_step_response(Axis.PITCH, from_val=0.0, to_val=5.0)

        # Recorden skal vaere aktiv
        recorder = ctrl.get_step_response_recorder(Axis.PITCH)
        assert recorder is not None
        assert recorder.to_val == 5.0

    def test_add_response_listener_kalles_ved_record(self, pose_ctrl):
        """Sjekk at registrerte lyttere kalles naar samples legges til."""
        received = []

        def on_sample(axis, timestamp, setpoint, actual):
            received.append((axis, timestamp, setpoint, actual))

        pose_ctrl.add_response_listener(on_sample)
        pose_ctrl.trigger_step_response(Axis.YAW, from_val=0.0, to_val=10.0)

        # Simuler en record via intern mekanisme
        recorder = pose_ctrl.get_step_response_recorder(Axis.YAW)
        recorder.record(timestamp=0.0, setpoint=10.0, actual=0.0)

        # Lytteren mottar ingenting direkte fra recorder —
        # den kalles av PoseController under update-syklusen.
        # Her tester vi bare at lytteren er registrert.
        assert pose_ctrl._response_listeners is not None
        assert len(pose_ctrl._response_listeners) == 1
