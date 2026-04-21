# test_hardware_imu_interface.py
# ===============================
# Tester for IMUInterface (abstrakt) og at LSM6DSOXDriver
# oppfyller kontrakten, inkludert kalibrerings-metoder.

import pytest

from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.hardware.imu_interface import IMUInterface
from stewart_platform.hardware.lsm6dsox_driver import LSM6DSOXDriver


class MockIMU(IMUInterface):
    """Mock-IMU for testing av abstrakt interface.

    Implementerer alle abstrakte metoder med enkle returverdier.
    Brukes for a verifisere at interfacet er komplett.
    """

    def __init__(self) -> None:
        self.gyro_calibrated = False
        self.accel_calibrated = False

    def configure(self, **kwargs) -> None:
        pass

    def read_acceleration(self) -> Vector3:
        return Vector3(0.0, 0.0, 9.81)

    def read_angular_velocity(self) -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    def read_temperature(self) -> float:
        return 25.0

    def who_am_i(self) -> int:
        return 0xFF

    def reset(self) -> None:
        pass

    def calibrate_gyro_bias(self) -> None:
        self.gyro_calibrated = True

    def calibrate_accelerometer_offset(self) -> None:
        self.accel_calibrated = True


class TestIMUInterfaceKontrakt:
    """Tester at IMUInterface definerer alle nodvendige metoder."""

    def test_mock_imu_kan_opprettes(self):
        """Sjekk at en komplett implementasjon kan instansieres."""
        imu = MockIMU()
        assert isinstance(imu, IMUInterface)

    def test_calibrate_gyro_bias_finnes(self):
        """Sjekk at calibrate_gyro_bias er definert i interfacet."""
        imu = MockIMU()
        imu.calibrate_gyro_bias()
        assert imu.gyro_calibrated is True

    def test_calibrate_accelerometer_offset_finnes(self):
        """Sjekk at calibrate_accelerometer_offset er definert i interfacet."""
        imu = MockIMU()
        imu.calibrate_accelerometer_offset()
        assert imu.accel_calibrated is True

    def test_read_acceleration_returnerer_vector3(self):
        """Sjekk at read_acceleration returnerer Vector3."""
        imu = MockIMU()
        accel = imu.read_acceleration()
        assert isinstance(accel, Vector3)

    def test_read_angular_velocity_returnerer_vector3(self):
        """Sjekk at read_angular_velocity returnerer Vector3."""
        imu = MockIMU()
        gyro = imu.read_angular_velocity()
        assert isinstance(gyro, Vector3)


class TestLSM6DSOXDriverKalibrering:
    """Tester at LSM6DSOXDriver har kalibrerings-metoder."""

    def test_calibrate_gyro_bias_finnes(self):
        """Sjekk at metoden eksisterer pa driveren."""
        assert hasattr(LSM6DSOXDriver, 'calibrate_gyro_bias')
        assert callable(getattr(LSM6DSOXDriver, 'calibrate_gyro_bias'))

    def test_calibrate_accelerometer_offset_finnes(self):
        """Sjekk at metoden eksisterer pa driveren."""
        assert hasattr(LSM6DSOXDriver, 'calibrate_accelerometer_offset')
        assert callable(getattr(LSM6DSOXDriver, 'calibrate_accelerometer_offset'))
