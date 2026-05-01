# test_gui_bridge_controller_bridge.py
# =====================================
# Tester for ControllerBridge i mock-modus.
#
# Bridge er det eneste tilkoblingspunktet mellom GUI og domene-laget.
# I mock-modus instansierer ikke bridge noen hardware — alle settere
# lagres internt og getterne returnerer simulerte verdier. Det gjor
# at vi kan teste hele bridge-API-et uten Pi, servoer eller IMU.

from pathlib import Path

import pytest

# PySide6 er en valgfri avhengighet — hopp over hele filen
# automatisk hvis den ikke er installert i miljoet.
PySide6 = pytest.importorskip("PySide6.QtCore")  # noqa: N816
from PySide6.QtCore import Qt

from stewart_platform.config.platform_config import (
    Axis,
    PIDGains,
    PlatformConfig,
    SafetyConfig,
)
from stewart_platform.geometry.pose import Pose
from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.gui.bridge.controller_bridge import (
    BridgeEvent,
    CalibrationResult,
    ControllerBridge,
)
from stewart_platform.gui.bridge.state_snapshot import StateSnapshot


@pytest.fixture
def bridge(tmp_path: Path) -> ControllerBridge:
    """Initialisert ControllerBridge i mock-modus."""
    cfg_path = tmp_path / "config.yaml"
    PlatformConfig().save(str(cfg_path))
    b = ControllerBridge(config_path=cfg_path, mock=True)
    b.initialize()
    return b


class TestBridgeInitialisering:
    """Tester for grunnleggende oppstart av ControllerBridge."""

    def test_initialize_lar_seg_kjore_to_ganger(self, bridge):
        """Sikrer at re-init i GUI ikke krasjer."""
        bridge.initialize()
        assert bridge.is_mock is True

    def test_config_settes_etter_initialize(self, bridge):
        """initialize() laster config og gjor den tilgjengelig."""
        assert isinstance(bridge.config, PlatformConfig)

    def test_initialize_med_manglende_fil_bruker_default(self, tmp_path):
        """Hvis YAML-filen ikke finnes faller bridge tilbake paa default."""
        cfg_path = tmp_path / "ikke-eksisterende.yaml"
        b = ControllerBridge(config_path=cfg_path, mock=True)
        b.initialize()
        assert isinstance(b.config, PlatformConfig)
        # Default skal vaere identisk med PlatformConfig() uten YAML.
        assert b.config.i2c_bus_number == PlatformConfig().i2c_bus_number


class TestBridgeSnapshot:
    """Tester for get_snapshot() i mock-modus."""

    def test_snapshot_returnerer_state_snapshot(self, bridge):
        snap = bridge.get_snapshot()
        assert isinstance(snap, StateSnapshot)

    def test_snapshot_inneholder_seks_servovinkler(self, bridge):
        snap = bridge.get_snapshot()
        assert len(snap.servo_angles) == 6

    def test_snapshot_har_alle_seks_pid_gains(self, bridge):
        snap = bridge.get_snapshot()
        for axis in Axis:
            assert axis in snap.pid_gains

    def test_snapshot_imu_akselerasjon_naer_g(self, bridge):
        """Mock-snapshot skal simulere ~1g paa Z-aksen."""
        snap = bridge.get_snapshot()
        assert 8.0 < snap.imu_acceleration.z < 11.0


class TestBridgeKommandoer:
    """Tester for set_target_pose, set_pid_gains, request_start/stop, home."""

    def test_set_target_pose_emitterer_signal(self, bridge):
        mottatt = []
        bridge.target_pose_changed.connect(mottatt.append, Qt.DirectConnection)
        ny_pose = Pose(translation=Vector3(1.0, 2.0, 3.0))
        ok = bridge.set_target_pose(ny_pose)
        assert ok is True
        assert len(mottatt) == 1
        assert mottatt[0].translation.x == 1.0

    def test_set_pid_gains_oppdaterer_per_akse(self, bridge):
        nye = PIDGains(kp=4.0, ki=0.2, kd=0.05)
        ok = bridge.set_pid_gains(Axis.ROLL, nye)
        assert ok is True
        snap = bridge.get_snapshot()
        # Etter set skal ROLL-aksen reflektere de nye verdiene.
        assert snap.pid_gains[Axis.ROLL].kp == 4.0
        # Andre akser skal vaere uendret (default).
        assert snap.pid_gains[Axis.PITCH].kp == PIDGains().kp

    def test_request_start_setter_running(self, bridge):
        bridge.request_start()
        snap = bridge.get_snapshot()
        assert snap.is_running is True

    def test_request_stop_setter_not_running(self, bridge):
        bridge.request_start()
        bridge.request_stop()
        snap = bridge.get_snapshot()
        assert snap.is_running is False

    def test_request_home_setter_target_til_origo(self, bridge):
        bridge.set_target_pose(Pose(translation=Vector3(5.0, 0.0, 0.0)))
        bridge.request_home()
        snap = bridge.get_snapshot()
        assert snap.target_pose.translation.x == 0.0


class TestBridgeNodstopp:
    """Tester for nodstopp-haandtering."""

    def test_trigger_e_stop_setter_e_stopped(self, bridge):
        bridge.trigger_e_stop("Manuell test")
        snap = bridge.get_snapshot()
        assert snap.is_e_stopped is True
        assert snap.e_stop_reason == "Manuell test"

    def test_reset_etter_estop_returnerer_true(self, bridge):
        bridge.trigger_e_stop("Test")
        ok = bridge.reset_latched_faults()
        assert ok is True
        snap = bridge.get_snapshot()
        assert snap.is_e_stopped is False

    def test_reset_uten_estop_returnerer_false(self, bridge):
        ok = bridge.reset_latched_faults()
        assert ok is False


class TestBridgeEventLog:
    """Tester for hendelsesloggen som overview/safety-tabs leser."""

    def test_eventloggen_har_innhold_etter_kommando(self, bridge):
        bridge.request_start()
        events = bridge.get_events()
        assert len(events) >= 1
        assert isinstance(events[0], BridgeEvent)

    def test_eventloggen_er_begrenset(self, bridge):
        # 100 er max-len; spam mer enn det og sjekk capping.
        for _ in range(150):
            bridge.request_start()
        events = bridge.get_events()
        assert len(events) <= 100


class TestBridgeKonfigurasjon:
    """Tester for update_config og save_config."""

    def test_update_config_aksepterer_gyldig_config(self, bridge):
        ny = PlatformConfig()
        ny.pid_gains = PIDGains(kp=5.0)
        feil = bridge.update_config(ny)
        assert feil == []
        assert bridge.config.pid_gains.kp == 5.0

    def test_update_config_avviser_ugyldig_config(self, bridge):
        ny = PlatformConfig()
        ny.base_radius = -1.0   # ugyldig — skal trigge validate-feil
        feil = bridge.update_config(ny)
        assert len(feil) >= 1

    def test_update_config_emitterer_signal(self, bridge):
        mottatt = []
        bridge.config_changed.connect(mottatt.append, Qt.DirectConnection)
        ny = PlatformConfig()
        bridge.update_config(ny)
        assert len(mottatt) == 1

    def test_update_safety_limits(self, bridge):
        nye_grenser = SafetyConfig(max_translation_mm=25.0)
        bridge.update_safety_limits(nye_grenser)
        assert bridge.config.safety_config.max_translation_mm == 25.0

    def test_save_config_skriver_fil(self, bridge):
        ok = bridge.save_config()
        assert ok is True
        assert bridge._config_path.exists()


class TestBridgeKalibrering:
    """Tester for IMU-kalibrering i mock-modus."""

    def test_calibrate_gyro_i_mock_returnerer_ok(self, bridge):
        result = bridge.calibrate_gyro()
        assert result is CalibrationResult.OK

    def test_calibrate_accelerometer_i_mock_returnerer_ok(self, bridge):
        result = bridge.calibrate_accelerometer()
        assert result is CalibrationResult.OK
