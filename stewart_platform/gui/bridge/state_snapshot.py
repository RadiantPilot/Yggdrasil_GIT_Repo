"""
state_snapshot.py · Én immutable dataclass som inneholder all
GUI-relevant tilstand på et gitt tidspunkt.

PollingWorker bygger et snapshot per tick og emitterer det. Alle
widgets leser det de trenger og ignorerer resten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ...config.platform_config import Axis, PIDGains
from ...geometry.pose import Pose
from ...geometry.vector3 import Vector3
from ...safety.safety_monitor import SafetyCheckResult


@dataclass(frozen=True)
class StateSnapshot:
    """Øyeblikksbilde av systemtilstand for GUI-lag.

    Dekker kun rotasjonell tilstand — plattformen styres rundt et
    fast sentrumspunkt og har ingen translasjon å rapportere.
    """

    timestamp: float = 0.0
    loop_frequency_hz: float = 0.0
    is_running: bool = False
    is_e_stopped: bool = False
    e_stop_reason: Optional[str] = None

    # Nåværende estimert orientering (fra IMU-fusjon).
    current_pose: Pose = field(default_factory=Pose.home)

    # Mål-orientering (setpunkt).
    target_pose: Pose = field(default_factory=Pose.home)

    # Servovinkler i grader (6 stk).
    servo_angles: List[float] = field(default_factory=lambda: [0.0] * 6)

    # IMU-akselerasjon i m/s² (bunnplate).
    imu_acceleration: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 9.81))

    # IMU-vinkelhastighet i °/s (bunnplate).
    imu_angular_velocity: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))

    # Estimert orientering (roll, pitch, yaw) i grader.
    imu_orientation: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    # PID-gains per akse (3 stk: ROLL, PITCH, YAW).
    pid_gains: Dict[Axis, PIDGains] = field(default_factory=dict)

    # PID-feil per akse (avvik fra setpunkt, grader).
    pid_errors: Dict[Axis, float] = field(default_factory=dict)

    latest_safety_result: Optional[SafetyCheckResult] = None
    safety_results: List[SafetyCheckResult] = field(default_factory=list)
