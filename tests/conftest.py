# conftest.py
# ===========
# Felles test-fixtures.

import pytest

from stewart_platform.config.platform_config import (
    PIDGains,
    PlatformConfig,
    SafetyConfig,
    ServoConfig,
)
from stewart_platform.geometry.pose import Pose
from stewart_platform.geometry.vector3 import Vector3


@pytest.fixture
def default_servo_config() -> ServoConfig:
    return ServoConfig()


@pytest.fixture
def default_pid_gains() -> PIDGains:
    return PIDGains()


@pytest.fixture
def default_safety_config() -> SafetyConfig:
    return SafetyConfig()


@pytest.fixture
def default_platform_config() -> PlatformConfig:
    return PlatformConfig()


@pytest.fixture
def six_servo_configs() -> list:
    return [
        ServoConfig(channel=i, mounting_angle_deg=i * 60.0)
        for i in range(6)
    ]


@pytest.fixture
def home_pose() -> Pose:
    return Pose.home()


@pytest.fixture
def zero_vector() -> Vector3:
    return Vector3(0.0, 0.0, 0.0)
