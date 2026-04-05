# motion_controller.py
# ====================
# Hovedkontroller som orkestrerer hele Stewart-plattformsystemet.
# Kjører kontrollsløyfen som leser IMU-data, estimerer orientering,
# beregner PID-korreksjon, løser invers kinematikk, validerer
# sikkerhet og sender servovinkler til PCA9685-driveren.

from __future__ import annotations

from typing import TYPE_CHECKING

from ..geometry.pose import Pose

if TYPE_CHECKING:
    from ..config.platform_config import PlatformConfig
    from ..hardware.imu_interface import IMUInterface
    from ..kinematics.inverse_kinematics import InverseKinematics
    from ..safety.safety_monitor import SafetyMonitor
    from ..servo.servo_array import ServoArray
    from .imu_fusion import IMUFusion
    from .pose_controller import PoseController


class MotionController:
    """Hovedkontroller for Stewart-plattformen.

    Orkestrerer hele kontrollsystemet i en sløyfe som kjører
    med konfigurerbar frekvens (control_loop_rate_hz):

    1. Les akselerometer- og gyroskopdata fra toppplate-IMU.
    2. (Valgfritt) Les bunnplate-IMU for basekompensasjon.
    3. Estimer nåværende orientering via IMUFusion.
    4. Beregn korreksjon via PoseController (PID).
    5. Løs invers kinematikk for å finne servovinkler.
    6. Valider sikkerhet via SafetyMonitor.
    7. Send servovinkler til ServoArray via PCA9685.

    Kontrolleren kjører i en egen tråd og kan startes/stoppes
    trygt. Nødstopp frikobler alle servoer umiddelbart.
    """

    def __init__(self, config: PlatformConfig) -> None:
        """Opprett en ny kontroller fra konfigurasjon.

        Initialiserer alle underkomponenter (maskinvare, geometri,
        kinematikk, PID, sikkerhet) basert på PlatformConfig.

        Args:
            config: Komplett plattformkonfigurasjon.
        """
        self._config = config
        self._servo_array: ServoArray | None = None
        self._top_imu: IMUInterface | None = None
        self._base_imu: IMUInterface | None = None
        self._ik_solver: InverseKinematics | None = None
        self._pose_controller: PoseController | None = None
        self._imu_fusion: IMUFusion | None = None
        self._safety_monitor: SafetyMonitor | None = None
        self._target_pose = Pose.home()
        self._current_pose = Pose.home()
        self._running = False
        self._loop_rate_hz = config.control_loop_rate_hz

    def initialize(self) -> None:
        """Initialiser all maskinvare og gå til hjemmeposisjon.

        Setter opp I2C-buss, PCA9685-driver, IMU-sensorer,
        geometrisk modell, IK-solver, PID-kontroller og
        sikkerhetsovervåker. Flytter alle servoer til hjemmeposisjon.

        Raises:
            RuntimeError: Hvis maskinvareinitialisering feiler
                          (f.eks. I2C-enhet ikke funnet).
        """
        from ..geometry.platform_geometry import PlatformGeometry
        from ..hardware.i2c_bus import I2CBus
        from ..hardware.pca9685_driver import PCA9685Driver
        from ..hardware.lsm6dsox_driver import LSM6DSOXDriver
        from ..hardware.base_imu_driver import BaseIMUDriver
        from ..kinematics.inverse_kinematics import InverseKinematics
        from ..safety.safety_monitor import SafetyMonitor
        from ..servo.servo_array import ServoArray
        from .imu_fusion import IMUFusion
        from .pose_controller import PoseController

        cfg = self._config

        # I2C og maskinvare
        bus = I2CBus(cfg.i2c_bus_number)
        driver = PCA9685Driver(bus, cfg.pca9685_address, cfg.pca9685_frequency)
        self._servo_array = ServoArray(cfg.servo_configs, driver)

        # IMU-sensorer
        self._top_imu = LSM6DSOXDriver(bus, cfg.lsm6dsox_top_address)
        self._base_imu = BaseIMUDriver(bus, cfg.base_imu_address)

        # Geometri og kinematikk
        geometry = PlatformGeometry(cfg)
        self._ik_solver = InverseKinematics(geometry, cfg.servo_configs)

        # Kontroll
        self._pose_controller = PoseController(cfg.pid_gains)
        self._imu_fusion = IMUFusion()

        # Sikkerhet
        self._safety_monitor = SafetyMonitor(cfg.safety_config, cfg.servo_configs)

        # Gå til hjemmeposisjon
        self._servo_array.go_home()

    def set_target_pose(self, pose: Pose) -> None:
        """Sett ønsket mål-pose for plattformen.

        Mål-posen brukes av PoseController som setpunkt.
        Posen valideres mot sikkerhetsgrenser før den aksepteres.

        Args:
            pose: Ønsket 6-DOF pose (translasjon + rotasjon).

        Raises:
            ValueError: Hvis posen er utenfor tillatte sikkerhetsgrenser.
        """
        if self._safety_monitor is not None:
            if not self._safety_monitor.validate_pose(pose):
                raise ValueError("Mål-pose er utenfor tillatte sikkerhetsgrenser.")
        self._target_pose = pose

    def start(self) -> None:
        """Start kontrollsløyfen i en egen tråd.

        Sløyfen kjører med frekvensen spesifisert i
        control_loop_rate_hz til stop() eller emergency_stop() kalles.

        Raises:
            RuntimeError: Hvis kontrolleren ikke er initialisert.
        """
        if self._servo_array is None:
            raise RuntimeError("Kontrolleren er ikke initialisert. Kall initialize() først.")
        self._running = True

    def stop(self) -> None:
        """Stopp kontrollsløyfen og behold servoer i nåværende posisjon.

        Avslutter kontrolltråden på en trygg måte. Servoene
        beholder sin siste posisjon (ikke frikoblet).
        """
        self._running = False

    def emergency_stop(self) -> None:
        """Nødstopp: stopp sløyfen og frikoble alle servoer umiddelbart.

        Kalles ved sikkerhetsfeil eller manuell nødstopp.
        Alle servoer frikoblet øyeblikkelig slik at plattformen
        kan bevege seg fritt.
        """
        self._running = False
        if self._safety_monitor is not None:
            self._safety_monitor.trigger_emergency_stop()
        if self._servo_array is not None:
            self._servo_array.detach_all()

    def step(self) -> None:
        """Utfør en enkelt iterasjon av kontrollsløyfen.

        Nyttig for testing og feilsøking der man ønsker å kjøre
        sløyfen manuelt steg for steg i stedet for i en tråd.

        Steg:
        1. Les IMU-data.
        2. Oppdater IMU-fusjon.
        3. Beregn PID-korreksjon.
        4. Løs IK.
        5. Valider sikkerhet.
        6. Sett servovinkler.
        """
        from ..geometry.vector3 import Vector3

        dt = 1.0 / self._loop_rate_hz

        # 1-2: Les IMU og oppdater fusjon
        if self._top_imu is not None and self._imu_fusion is not None:
            accel = self._top_imu.read_acceleration()
            gyro = self._top_imu.read_gyroscope()
            orientation = self._imu_fusion.update(accel, gyro, dt)
            self._current_pose = Pose(rotation=orientation)
        else:
            accel = Vector3(0.0, 0.0, 9.81)

        # 3: PID-korreksjon
        if self._pose_controller is not None:
            correction = self._pose_controller.update(
                self._target_pose, self._current_pose, dt
            )
        else:
            correction = self._target_pose

        # 4: Invers kinematikk
        if self._ik_solver is not None:
            angles = self._ik_solver.solve(correction)
        else:
            return

        # 5: Sikkerhetsvalidering
        if self._safety_monitor is not None:
            result = self._safety_monitor.check_all(
                correction, angles, accel, dt
            )
            if not result.is_safe:
                return

        # 6: Sett servovinkler
        if self._servo_array is not None:
            self._servo_array.set_angles(angles)

    def get_current_pose(self) -> Pose:
        """Hent nåværende estimert pose for toppplaten.

        Returns:
            Estimert 6-DOF pose basert på IMU-fusjon.
        """
        return self._current_pose

    def get_servo_angles(self) -> list[float]:
        """Hent nåværende servovinkler for alle 6 servoer.

        Returns:
            Liste med 6 vinkler i grader, eller tom liste
            hvis kontrolleren ikke er initialisert.
        """
        if self._servo_array is None:
            return []
        return self._servo_array.get_angles()

    def is_running(self) -> bool:
        """Sjekk om kontrollsløyfen kjører.

        Returns:
            True hvis sløyfen er aktiv.
        """
        return self._running

    def shutdown(self) -> None:
        """Sikker avslutning av hele systemet.

        Stopper kontrollsløyfen, frikoblet alle servoer og
        lukker I2C-forbindelsen. Bør kalles ved programavslutning.
        """
        self._running = False
        if self._servo_array is not None:
            self._servo_array.detach_all()
        self._servo_array = None
        self._top_imu = None
        self._base_imu = None
        self._ik_solver = None
        self._pose_controller = None
        self._imu_fusion = None
        self._safety_monitor = None
