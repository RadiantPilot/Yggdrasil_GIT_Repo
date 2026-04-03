# conftest.py
# ===========
# Felles test-fixtures for hele testsuiten.
# Gir ferdigkonfigurerte objekter som brukes pa tvers av testfiler.

import pytest

from stewart_platform.config.platform_config import (
    PlatformConfig,
    ServoConfig,
    PIDGains,
    SafetyConfig,
)
from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.geometry.pose import Pose


# ---------------------------------------------------------------------------
# Config-fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_servo_config() -> ServoConfig:
    """Standard servokonfigurasjon med standardverdier."""
    return ServoConfig()


@pytest.fixture
def default_pid_gains() -> PIDGains:
    """Standard PID-forsterkning med standardverdier."""
    return PIDGains()


@pytest.fixture
def default_safety_config() -> SafetyConfig:
    """Standard sikkerhetsgrenser med standardverdier."""
    return SafetyConfig()


@pytest.fixture
def default_platform_config() -> PlatformConfig:
    """Komplett standard plattformkonfigurasjon.

    Bruker standardverdier som matcher config/default_config.yaml.
    """
    return PlatformConfig()


@pytest.fixture
def six_servo_configs() -> list:
    """Liste med 6 servokonfigurasjoner med ulike kanaler og monteringsvinkler."""
    return [
        ServoConfig(channel=i, mounting_angle_deg=i * 60.0)
        for i in range(6)
    ]


# ---------------------------------------------------------------------------
# Geometry-fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def zero_vector() -> Vector3:
    """Nullvektor (0, 0, 0)."""
    return Vector3(0.0, 0.0, 0.0)


@pytest.fixture
def unit_x() -> Vector3:
    """Enhetsvektor i X-retning (1, 0, 0)."""
    return Vector3(1.0, 0.0, 0.0)


@pytest.fixture
def unit_y() -> Vector3:
    """Enhetsvektor i Y-retning (0, 1, 0)."""
    return Vector3(0.0, 1.0, 0.0)


@pytest.fixture
def unit_z() -> Vector3:
    """Enhetsvektor i Z-retning (0, 0, 1)."""
    return Vector3(0.0, 0.0, 1.0)


@pytest.fixture
def home_pose() -> Pose:
    """Hjemmepose (alle verdier null)."""
    return Pose.home()
