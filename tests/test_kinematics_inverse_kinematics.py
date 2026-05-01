# test_kinematics_inverse_kinematics.py
# ======================================
# Tester for InverseKinematics-klassen.
#
# InverseKinematics er det matematiske hjertet i systemet.
# Den tar en onsket 6-DOF pose og beregner de 6 servovinklene
# som trengs for a oppna den posen. Korrekt IK er avgjorende
# for at plattformen beveger seg dit den skal.
#
# GUI-relevans:
#   Nar brukeren setter en mal-pose via GUI-en (sliders for
#   X, Y, Z, roll, pitch, yaw), loper den gjennom IK-solveren
#   for a finne servovinkler. GUI-en viser ogsa om en pose
#   er oppnaelig (is_pose_reachable) og arbeidsomradets grenser
#   (get_workspace_bounds) for visualisering.

import pytest

from stewart_platform.config.platform_config import PlatformConfig, ServoConfig
from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.geometry.pose import Pose
from stewart_platform.geometry.platform_geometry import PlatformGeometry
from stewart_platform.kinematics.inverse_kinematics import InverseKinematics


@pytest.fixture
def ik_solver(default_platform_config):
    """Standard IK-solver med standard geometri og servokonfigurasjon."""
    geo = PlatformGeometry(default_platform_config)
    return InverseKinematics(geo, default_platform_config.servo_configs)


class TestInverseKinematicsOpprettelse:
    """Tester for opprettelse av IK-solver."""

    def test_opprettelse(self, ik_solver):
        """Sjekk at IK-solveren kan opprettes med standard konfigurasjon."""
        assert ik_solver is not None

    def test_lagrer_geometri(self, default_platform_config):
        """Sjekk at IK-solveren lagrer referanse til geometri."""
        geo = PlatformGeometry(default_platform_config)
        ik = InverseKinematics(geo, default_platform_config.servo_configs)
        assert ik._geometry is geo

    def test_lagrer_servo_configs(self, default_platform_config):
        """Sjekk at IK-solveren lagrer servokonfigurasjonene."""
        geo = PlatformGeometry(default_platform_config)
        ik = InverseKinematics(geo, default_platform_config.servo_configs)
        assert len(ik._servo_configs) == 6


class TestInverseKinematiksSolve:
    """Tester for selve IK-losningen (pose -> 6 servovinkler).

    Dette er den viktigste testen: gitt en pose, skal solveren
    returnere 6 gyldige servovinkler.
    """

    def test_solve_hjemmepose_gir_seks_vinkler(self, ik_solver):
        """Sjekk at IK for hjemmepose returnerer 6 servovinkler.

        Hjemmeposen er det enkleste tilfellet — alle bein er like lange
        og alle servoer skal sta i hjemmeposisjon.
        """
        pose = Pose.home()
        vinkler = ik_solver.solve(pose)
        assert len(vinkler) == 6

    def test_solve_hjemmepose_vinkler_er_like(self, ik_solver):
        """Sjekk at hjemmeposen gir like vinkler for alle servoer.

        Pa grunn av symmetrien skal alle 6 servoer staa i omtrent
        samme vinkel ved hjemmepose.
        """
        pose = Pose.home()
        vinkler = ik_solver.solve(pose)
        gjennomsnitt = sum(vinkler) / len(vinkler)
        for vinkel in vinkler:
            assert vinkel == pytest.approx(gjennomsnitt, abs=1.0)

    def test_solve_hjemmepose_vinkler_innenfor_grenser(self, ik_solver):
        """Sjekk at IK-vinkler for hjemmepose er innenfor servogrensene."""
        pose = Pose.home()
        vinkler = ik_solver.solve(pose)
        for vinkel in vinkler:
            assert 0.0 <= vinkel <= 180.0

    def test_solve_liten_translasjon(self, ik_solver):
        """Sjekk at en liten translasjon i Z gir gyldige vinkler.

        En liten heving av plattformen skal gi vinkler som er
        litt forskjellige fra hjemmeposisjonen.
        """
        pose = Pose(translation=Vector3(0.0, 0.0, 5.0))
        vinkler = ik_solver.solve(pose)
        assert len(vinkler) == 6
        for vinkel in vinkler:
            assert 0.0 <= vinkel <= 180.0

    def test_solve_liten_rotasjon(self, ik_solver):
        """Sjekk at en liten roll-rotasjon gir gyldige men ulike vinkler.

        En roll-bevegelse skal gi asymmetriske vinkler — den ene siden
        heves mens den andre senkes.
        """
        pose = Pose(rotation=Vector3(5.0, 0.0, 0.0))
        vinkler = ik_solver.solve(pose)
        assert len(vinkler) == 6
        # Vinklene skal ikke alle vaere like (plattformen er vippet)
        assert not all(v == pytest.approx(vinkler[0], abs=0.1) for v in vinkler)

    def test_solve_uoppnaelig_pose_kaster_feil(self, ik_solver):
        """Sjekk at en umulig pose kaster ValueError.

        En ekstrem pose der beinlengdene overstiger fysiske grenser
        skal gi en tydelig feilmelding.
        """
        pose = Pose(translation=Vector3(0.0, 0.0, 500.0))  # Altfor hoyt
        with pytest.raises(ValueError):
            ik_solver.solve(pose)


class TestPoseReachability:
    """Tester for sjekk av om en pose er fysisk oppnaelig.

    GUI-en bruker dette for a markere ugyldig omrade i
    arbeidsomrade-visualiseringen.
    """

    def test_hjemmepose_er_oppnaelig(self, ik_solver):
        """Sjekk at hjemmeposen alltid er oppnaelig."""
        pose = Pose.home()
        assert ik_solver.is_pose_reachable(pose) is True

    def test_liten_bevegelse_er_oppnaelig(self, ik_solver):
        """Sjekk at sma bevegelser rundt hjemmepose er oppnaelige."""
        poser = [
            Pose(translation=Vector3(5.0, 0.0, 0.0)),
            Pose(translation=Vector3(0.0, 5.0, 0.0)),
            Pose(translation=Vector3(0.0, 0.0, 5.0)),
            Pose(rotation=Vector3(3.0, 0.0, 0.0)),
            Pose(rotation=Vector3(0.0, 3.0, 0.0)),
            Pose(rotation=Vector3(0.0, 0.0, 3.0)),
        ]
        for pose in poser:
            assert ik_solver.is_pose_reachable(pose) is True

    def test_ekstrem_pose_er_ikke_oppnaelig(self, ik_solver):
        """Sjekk at en ekstrem pose (langt utenfor arbeidsomradet) ikke er oppnaelig."""
        pose = Pose(translation=Vector3(500.0, 500.0, 500.0))
        assert ik_solver.is_pose_reachable(pose) is False


class TestWorkspaceBounds:
    """Tester for estimering av arbeidsomradets grenser.

    GUI-en bruker dette for a sette slider-grenser og vise
    arbeidsomradet visuelt.
    """

    def test_workspace_bounds_returnerer_to_poser(self, ik_solver):
        """Sjekk at workspace bounds returnerer (min_pose, max_pose)."""
        min_pose, max_pose = ik_solver.get_workspace_bounds()
        assert isinstance(min_pose, Pose)
        assert isinstance(max_pose, Pose)

    def test_workspace_min_er_negativ_og_max_positiv(self, ik_solver):
        """Sjekk at min-pose har negative verdier og max-pose har positive.

        Arbeidsomradet skal vaere symmetrisk rundt origo.
        """
        min_pose, max_pose = ik_solver.get_workspace_bounds()
        assert min_pose.translation.x <= 0.0
        assert max_pose.translation.x >= 0.0
        assert min_pose.rotation.x <= 0.0
        assert max_pose.rotation.x >= 0.0

    def test_workspace_bounds_er_realistiske(self, ik_solver):
        """Sjekk at arbeidsomradet er innenfor realistiske verdier.

        For en plattform med 150mm stag og 25mm servoarm forventes
        et relativt begrenset arbeidsomrade.
        """
        min_pose, max_pose = ik_solver.get_workspace_bounds()
        # Translasjon skal vaere under rod_length
        assert max_pose.translation.x < 150.0
        assert max_pose.translation.y < 150.0
        assert max_pose.translation.z < 150.0


class TestIKDirectionUavhengig:
    """Regresjonstest: IK skal returnere ren geometrisk vinkel.

    Tidligere flippet IK vinkelen (180 - alpha) for servoer med
    direction=-1, og Servo.angle_to_pulse_us flippet en gang til.
    Dobbel inversjon brot kalibrering for inverterte servoer.
    Etter fiksen skal IK gi samme vinkel uavhengig av direction.
    """

    def test_direction_paavirker_ikke_ik_output(self, default_platform_config):
        """Sjekk at direction=-1 gir samme IK-vinkel som direction=+1.

        IK skal vaere ren geometri; rotasjonsretning hører hjemme i
        Servo-laget naar pulsbredden beregnes.
        """
        from stewart_platform.config.platform_config import ServoConfig
        from stewart_platform.geometry.platform_geometry import PlatformGeometry

        geo = PlatformGeometry(default_platform_config)
        configs_pluss = [
            ServoConfig(channel=i, mounting_angle_deg=i * 60.0, direction=1)
            for i in range(6)
        ]
        configs_minus = [
            ServoConfig(channel=i, mounting_angle_deg=i * 60.0, direction=-1)
            for i in range(6)
        ]
        ik_pluss = InverseKinematics(geo, configs_pluss)
        ik_minus = InverseKinematics(geo, configs_minus)

        pose = Pose(translation=Vector3(0.0, 0.0, 5.0))
        vinkler_pluss = ik_pluss.solve(pose)
        vinkler_minus = ik_minus.solve(pose)

        for v_p, v_m in zip(vinkler_pluss, vinkler_minus):
            assert v_p == pytest.approx(v_m, abs=1e-9)
