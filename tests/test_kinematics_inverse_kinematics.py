# test_kinematics_inverse_kinematics.py
# ======================================
# Tester for InverseKinematics — kjernen i styringen.
# Plattformen styres kun rotasjonelt.

import pytest

from stewart_platform.config.platform_config import PlatformConfig, ServoConfig
from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.geometry.pose import Pose
from stewart_platform.geometry.platform_geometry import PlatformGeometry
from stewart_platform.kinematics.inverse_kinematics import InverseKinematics


@pytest.fixture
def ik_solver(default_platform_config):
    """Standard IK-solver med standard geometri."""
    geo = PlatformGeometry(default_platform_config)
    return InverseKinematics(geo, default_platform_config.servo_configs)


class TestSolve:
    """IK skal returnere 6 gyldige servovinkler for vanlige rotasjoner."""

    def test_hjemmepose_gir_seks_vinkler(self, ik_solver):
        vinkler = ik_solver.solve(Pose.home())
        assert len(vinkler) == 6

    def test_hjemmepose_vinkler_er_like(self, ik_solver):
        vinkler = ik_solver.solve(Pose.home())
        gjennomsnitt = sum(vinkler) / len(vinkler)
        for vinkel in vinkler:
            assert vinkel == pytest.approx(gjennomsnitt, abs=1.0)

    def test_hjemmepose_vinkler_innenfor_grenser(self, ik_solver):
        vinkler = ik_solver.solve(Pose.home())
        for vinkel in vinkler:
            assert 0.0 <= vinkel <= 180.0

    def test_liten_roll_gir_asymmetriske_vinkler(self, ik_solver):
        """Liten rotasjon i roll skal heve én side og senke den andre."""
        vinkler = ik_solver.solve(Pose(rotation=Vector3(5.0, 0.0, 0.0)))
        assert len(vinkler) == 6
        assert not all(v == pytest.approx(vinkler[0], abs=0.1) for v in vinkler)

    def test_uoppnaelig_pose_klemmer(self, ik_solver):
        """Pose utenfor workspace skal klemmes — ikke kaste."""
        vinkler = ik_solver.solve(Pose(rotation=Vector3(80.0, 0.0, 0.0)))
        assert len(vinkler) == 6
        for i, vinkel in enumerate(vinkler):
            sc = ik_solver._servo_configs[i]
            assert sc.min_angle_deg <= vinkel <= sc.max_angle_deg
        assert ik_solver.last_solve_clamped is True


class TestPoseReachability:
    def test_hjemmepose_er_oppnaelig(self, ik_solver):
        assert ik_solver.is_pose_reachable(Pose.home()) is True

    def test_liten_rotasjon_er_oppnaelig(self, ik_solver):
        for r in [
            Vector3(3.0, 0.0, 0.0),
            Vector3(0.0, 3.0, 0.0),
            Vector3(0.0, 0.0, 3.0),
        ]:
            assert ik_solver.is_pose_reachable(Pose(rotation=r)) is True

    def test_ekstrem_rotasjon_er_ikke_oppnaelig(self, ik_solver):
        assert ik_solver.is_pose_reachable(Pose(rotation=Vector3(80.0, 0.0, 0.0))) is False


class TestIKDirectionUavhengig:
    """IK skal returnere ren geometrisk vinkel — direction håndteres
    av Servo.angle_to_pulse_us, ikke av IK selv."""

    def test_direction_paavirker_ikke_ik_output(self, default_platform_config):
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

        pose = Pose(rotation=Vector3(2.0, 1.0, 0.0))
        vinkler_pluss = ik_pluss.solve(pose)
        vinkler_minus = ik_minus.solve(pose)

        for v_p, v_m in zip(vinkler_pluss, vinkler_minus):
            assert v_p == pytest.approx(v_m, abs=1e-9)
