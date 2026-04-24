"""
state_snapshot.py · Én immutable dataclass som inneholder all
GUI-relevant tilstand på et gitt tidspunkt.

PollingWorker bygger et snapshot per tick og emitterer det. Alle
widgets leser det de trenger og ignorerer resten. Dette gir:
- Konsistente verdier innenfor én frame (alt er lest i samme tick).
- Enkel mocking for testing (bygg et snapshot manuelt).
- Lett å serialisere for logging/replay senere.
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

    Bygges av PollingWorker én gang per tick. Widgets leser kun
    det de trenger — feltene de ignorerer har ingen kostnad.
    """

    # Tidspunkt da snapshot ble tatt (unix-tid, sekunder).
    timestamp: float = 0.0

    # Målt loop-frekvens siden forrige snapshot (Hz).
    loop_frequency_hz: float = 0.0

    # True hvis kontroll-loopen kjører.
    is_running: bool = False

    # True hvis E-STOP er utløst.
    is_e_stopped: bool = False

    # Årsak til eventuell E-STOP.
    e_stop_reason: Optional[str] = None

    # Nåværende estimert pose (fra IMU-fusjon).
    current_pose: Pose = field(default_factory=Pose.home)

    # Nåværende mål-pose (setpunkt).
    target_pose: Pose = field(default_factory=Pose.home)

    # Nåværende servovinkler (6 stk, grader).
    servo_angles: List[float] = field(default_factory=lambda: [0.0] * 6)

    # IMU-akselerasjon i m/s² (bunnplate).
    imu_acceleration: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 9.81))

    # IMU-vinkelhastighet i °/s (bunnplate).
    imu_angular_velocity: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))

    # Estimert orientering (roll, pitch, yaw) i grader.
    imu_orientation: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    # PID-gains per akse.
    pid_gains: Dict[Axis, PIDGains] = field(default_factory=dict)

    # PID-feil per akse (nåværende avvik fra setpunkt).
    pid_errors: Dict[Axis, float] = field(default_factory=dict)

    # Siste sikkerhets-check (None hvis ikke tilgjengelig).
    latest_safety_result: Optional[SafetyCheckResult] = None

    # Historikk over sikkerhetssjekker (for safety-tab).
    safety_results: List[SafetyCheckResult] = field(default_factory=list)
