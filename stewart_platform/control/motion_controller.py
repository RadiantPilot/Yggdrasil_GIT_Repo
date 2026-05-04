# motion_controller.py
# ====================
# Hovedkontroller som orkestrerer hele Stewart-plattformsystemet.
# Kjører kontrollsløyfen som leser IMU-data, estimerer orientering,
# beregner PID-korreksjon, løser invers kinematikk, validerer
# sikkerhet og sender servovinkler til PCA9685-driveren.

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional, TYPE_CHECKING

from ..geometry.pose import Pose
from ..geometry.vector3 import Vector3
from ..safety.safety_monitor import SafetySeverity

if TYPE_CHECKING:
    from ..config.platform_config import PlatformConfig
    from ..hardware.i2c_bus import I2CBus
    from ..hardware.imu_interface import IMUInterface
    from ..kinematics.inverse_kinematics import InverseKinematics
    from ..safety.safety_monitor import SafetyMonitor
    from ..servo.servo_array import ServoArray
    from .imu_fusion import IMUFusion
    from .pose_controller import PoseController


# Callback-signatur for sikkerhetsbrudd som motion-loopen møter.
# Kalles med (severity, liste-med-bruddmeldinger).
SafetyViolationListener = Callable[[SafetySeverity, List[str]], None]

# Callback-signatur for uventede unntak fra kontroll-tråden.
# Kalles med selve exception-objektet for logging/visning.
LoopErrorListener = Callable[[BaseException], None]


class MotionController:
    """Hovedkontroller for Stewart-plattformen.

    Orkestrerer hele kontrollsystemet i en sløyfe som kjører
    med konfigurerbar frekvens (control_loop_rate_hz):

    1. Les akselerometer- og gyroskopdata fra bunnplate-IMU (LSM6DSOXTR).
    2. Estimer bunnplatens orientering via IMUFusion.
    3. Beregn kompensasjon via PoseController (PID) som motvirker bunnplatens tilt.
    4. Løs invers kinematikk for å finne servovinkler.
    5. Valider sikkerhet via SafetyMonitor.
    6. Send servovinkler til ServoArray via PCA9685.

    start() spinner opp en daemon-tråd som kaller step() med
    konfigurert frekvens. stop() / shutdown() avslutter den
    trygt via threading.Event. Delt mutable tilstand (target_pose,
    current_pose) er beskyttet av et internt lock slik at GUI-tråden
    og kontroll-tråden kan jobbe trygt mot samme objekt.
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
        self._base_imu: IMUInterface | None = None
        self._ik_solver: InverseKinematics | None = None
        self._pose_controller: PoseController | None = None
        self._imu_fusion: IMUFusion | None = None
        self._safety_monitor: SafetyMonitor | None = None
        self._bus: I2CBus | None = None
        self._target_pose = Pose.home()
        self._current_pose = Pose.home()
        # Siste IMU-data fra step(). Brukes av GUI-polling for å unngå
        # konkurrerende I2C-lesninger mot kontroll-tråden. Beskyttes av
        # samme _lock som target/current_pose.
        self._last_accel = Vector3(0.0, 0.0, 9.81)
        self._last_gyro = Vector3(0.0, 0.0, 0.0)
        self._last_orientation = Vector3(0.0, 0.0, 0.0)
        self._loop_rate_hz = config.control_loop_rate_hz
        self._safety_listeners: List[SafetyViolationListener] = []
        self._error_listeners: List[LoopErrorListener] = []
        # Teller for konsekutive IK-feil (kun ekte unntak, ikke
        # klemming). IK klemmer/fryser nå marginale poser i stedet
        # for å kaste, så denne telleren utløses primært av
        # degenerert geometri (R < 1e-10). Brukes ikke lenger til
        # e-stop — kun til diagnostikk og throttlet ERROR-varsling.
        self._consecutive_ik_failures = 0
        # Forrige tick sin klemmingstilstand. Brukes for å varsle
        # GUI kun ved tilstandsovergang (ikke 50 Hz spam).
        self._previous_clamp_state = False
        # Forrige tick sin safety-status. Når safety_monitor rapporterer
        # brudd hver iterasjon (typisk hastighetsbrudd pga IMU-støy +
        # 50 Hz PID-output-svingning), vil 50 Hz signal-emit pakke
        # Qt-signalkøen og gjøre GUI-en uresponsiv. Vi varsler derfor
        # kun ved overgang safe→unsafe og endret bruddmengde.
        self._previous_safety_safe = True
        self._last_safety_violations: List[str] = []

        # Trådhåndtering. Lock beskytter target/current pose mellom
        # GUI-tråd og kontrolltråd. Event signaliserer at løkken
        # skal stoppe (responsivt — kontrolltråden venter på den
        # mellom hvert tick i stedet for time.sleep).
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._stop_event.set()  # Ingen tråd kjører enda
        self._thread: Optional[threading.Thread] = None

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
        from ..kinematics.inverse_kinematics import InverseKinematics
        from ..safety.safety_monitor import SafetyMonitor
        from ..servo.servo_array import ServoArray
        from .imu_fusion import IMUFusion
        from .pose_controller import PoseController

        cfg = self._config

        # I2C og maskinvare. Bussen lagres på self slik at shutdown()
        # kan lukke fd-en og unngå lekkasje når controller blir
        # reinitialisert (f.eks. ved konfig-endring i GUI).
        self._bus = I2CBus(cfg.i2c_bus_number)
        driver = PCA9685Driver(self._bus, cfg.pca9685_address, cfg.pca9685_frequency)
        # Vekker PCA9685 fra sleep og setter PWM-frekvens.
        # Uten dette gir den ingen utgang selv om alle write_byte_data lykkes.
        driver.reset()
        self._servo_array = ServoArray(cfg.servo_configs, driver)

        # IMU-sensor (bunnplate)
        self._base_imu = LSM6DSOXDriver(self._bus, cfg.lsm6dsox_address)
        # Tilbakestill og konfigurer sensoren før bruk.
        # Uten configure() kjører sensoren i power-down og gir 0-er.
        self._base_imu.reset()
        self._base_imu.configure()

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

        # Pre-fyll IMU-cache slik at GUI-polling kan lese fra cache fra
        # første tick — uten dette ville snapshot vise nuller helt til
        # brukeren trykker Start og kontroll-tråden begynner å kjøre.
        if self._base_imu is not None and self._imu_fusion is not None:
            accel = self._base_imu.read_acceleration()
            gyro = self._base_imu.read_angular_velocity()
            orient = self._imu_fusion.update(accel, gyro, 1.0 / self._loop_rate_hz)
            with self._lock:
                self._last_accel = accel
                self._last_gyro = gyro
                self._last_orientation = orient

    def set_target_pose(self, pose: Pose) -> bool:
        """Sett ønsket mål-pose for plattformen.

        Mål-posen brukes av PoseController som setpunkt.
        Posen valideres mot sikkerhetsgrenser før den aksepteres.

        Args:
            pose: Ønsket 6-DOF pose (translasjon + rotasjon).

        Returns:
            True hvis posen ble akseptert, False hvis den ble avvist.
        """
        if self._safety_monitor is not None:
            if not self._safety_monitor.validate_pose(pose):
                return False
        with self._lock:
            self._target_pose = pose
        return True

    def home(self) -> None:
        """Flytt plattformen til hjemmeposisjon.

        Resetter mål-pose til home og delegerer til
        ServoArray.go_home() for å flytte servoene.
        """
        with self._lock:
            self._target_pose = Pose.home()
        if self._servo_array is not None:
            self._servo_array.go_home()

    def start(self) -> None:
        """Start kontrollsløyfen i en egen tråd.

        Sløyfen kjører med frekvensen spesifisert i
        control_loop_rate_hz til stop() eller emergency_stop() kalles.
        Kall to ganger på rad er trygt — eksisterende tråd
        gjenbrukes.

        Raises:
            RuntimeError: Hvis kontrolleren ikke er initialisert.
        """
        if self._servo_array is None:
            raise RuntimeError(
                "Kontrolleren er ikke initialisert. Kall initialize() først."
            )
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="motion-loop", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stopp kontrollsløyfen og behold servoer i nåværende posisjon.

        Avslutter kontrolltråden på en trygg måte. Servoene
        beholder sin siste posisjon (ikke frikoblet). Trygg å
        kalle flere ganger eller når ingen tråd kjører.
        """
        self._stop_event.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        self._thread = None

    def emergency_stop(self, reason: str | None = None) -> None:
        """Nødstopp: stopp sløyfen og frikoble alle servoer umiddelbart.

        Kalles ved sikkerhetsfeil eller manuell nødstopp.
        Alle servoer frikoblet øyeblikkelig slik at plattformen
        kan bevege seg fritt.

        Args:
            reason: Valgfri årsak. Hvis oppgitt brukes denne. Hvis
                    None, og safety-monitoren allerede har en mer
                    spesifikk grunn (f.eks. "Kritisk sikkerhetsbrudd"),
                    beholdes den. Ellers brukes en generisk fallback.
        """
        # Signaliser stopp først, men ikke vent (vi kan kalles fra
        # innsiden av selve tråden via step() ved CRITICAL-brudd —
        # join på seg selv ville hengt for alltid).
        self._stop_event.set()
        if self._safety_monitor is not None:
            if reason is not None:
                self._safety_monitor.trigger_e_stop(reason)
            elif self._safety_monitor.e_stop_reason is None:
                self._safety_monitor.trigger_e_stop("Nødstopp fra MotionController")
        if self._servo_array is not None:
            self._servo_array.detach_all()

    def _run(self) -> None:
        """Hovedløkka som kjører i kontroll-tråden.

        Bruker monotonic-klokken med next_tick-akkumulasjon for å
        holde frekvensen jevn selv om enkeltsteg tar litt forskjellig
        tid. stop_event.wait gjør stop() responsiv — vi venter med
        den i stedet for time.sleep slik at avslutning ikke blir
        forsinket av et nettopp-startet sleep-intervall.
        """
        period = 1.0 / self._loop_rate_hz
        next_tick = time.monotonic()
        while not self._stop_event.is_set():
            try:
                self.step()
            except BaseException as exc:
                # En uventet feil i selve sløyfen er trolig en
                # hardware-feil eller en programmeringsfeil. Gå
                # rett til e-stop, varsle lyttere, og avslutt
                # tråden i stedet for å spinne videre med ukjent
                # tilstand. Send selve unntaks-teksten som grunn
                # slik at brukeren ser hva som faktisk feilet.
                try:
                    self.emergency_stop(reason=f"Loop-feil: {exc!s}")
                except BaseException:  # noqa: BLE001 — defensiv
                    pass
                self._notify_loop_error(exc)
                return
            next_tick += period
            wait = next_tick - time.monotonic()
            if wait > 0:
                # Event.wait returnerer True om event ble satt mens
                # vi ventet → da hopper vi rett ut av løkka.
                if self._stop_event.wait(timeout=wait):
                    return
            else:
                # Vi er bak skjema — resync klokken slik at vi ikke
                # bygger opp etterslep og dermed kjører "raskere
                # enn fritt fall" en periode.
                next_tick = time.monotonic()

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
        dt = 1.0 / self._loop_rate_hz

        # 1-2: Les bunnplate-IMU og oppdater fusjon
        if self._base_imu is not None and self._imu_fusion is not None:
            accel = self._base_imu.read_acceleration()
            gyro = self._base_imu.read_angular_velocity()
            base_orientation = self._imu_fusion.update(accel, gyro, dt)
            new_current = Pose(rotation=base_orientation)
            with self._lock:
                self._current_pose = new_current
                self._last_accel = accel
                self._last_gyro = gyro
                self._last_orientation = base_orientation
        else:
            accel = Vector3(0.0, 0.0, 9.81)

        # Plukk ut delt tilstand under lock for å unngå at GUI-tråd
        # endrer mål-posen midt i en iterasjon.
        with self._lock:
            target = self._target_pose
            current = self._current_pose

        # 3: PID-korreksjon
        if self._pose_controller is not None:
            correction = self._pose_controller.update(target, current, dt)
        else:
            correction = target

        # 4: Invers kinematikk. IK klemmer/fryser nå marginale poser
        # automatisk og kaster bare ValueError ved degenerert
        # geometri. Når klemming skjer leser vi last_solve_clamped
        # for å gi GUI en WARNING ved tilstandsovergang.
        if self._ik_solver is None:
            return
        try:
            angles = self._ik_solver.solve(correction)
        except ValueError as ik_exc:
            self._consecutive_ik_failures += 1
            # Logg kun den første feilen — å spamme signalkøen 50
            # ganger per sekund kan gjøre GUI-en uresponsiv. Vi
            # e-stopper ikke lenger ved gjentatte feil; klemming gjør
            # det stort sett unødvendig, og en e-stop som ikke kan
            # nullstilles fra GUI-en er verre enn å la operatøren
            # se WARNING-en og ta affære.
            if self._consecutive_ik_failures == 1:
                self._notify_safety_violations(
                    SafetySeverity.WARNING,
                    [f"IK kastet unntak (degenerert geometri?): {ik_exc}"],
                )
            return
        # IK lyktes — nullstill teller for ekte unntak.
        self._consecutive_ik_failures = 0

        # Klemming-deteksjon: varsle kun ved tilstandsovergang slik at
        # vi ikke pakker Qt-signalkøen. Når klemming starter, send
        # WARNING med hvilke servoer som er klemt. Når den slutter,
        # send INFO-aktig WARNING for å indikere at vi er tilbake i
        # workspace.
        clamped_now = self._ik_solver.last_solve_clamped
        if clamped_now and not self._previous_clamp_state:
            mask = self._ik_solver.last_clamped_mask
            klemte = [str(i) for i, c in enumerate(mask) if c]
            self._notify_safety_violations(
                SafetySeverity.WARNING,
                [
                    f"IK klemmer pose — servo(er) {','.join(klemte)} "
                    f"holdes på siste gyldige posisjon."
                ],
            )
        elif not clamped_now and self._previous_clamp_state:
            self._notify_safety_violations(
                SafetySeverity.WARNING,
                ["IK klemming opphørt — pose tilbake innenfor workspace."],
            )
        self._previous_clamp_state = clamped_now

        # 5: Sikkerhetsvalidering. Bruddene varsles til registrerte
        # lyttere (typisk GUI) slik at de blir synlige istedenfor å
        # bare la step() returnere stille. CRITICAL utløser nødstopp
        # i check_all selv; ERROR avviser kommandoen men holder
        # løkka i live; WARNING tillater kommando med logging.
        if self._safety_monitor is not None:
            result = self._safety_monitor.check_all(
                correction, angles, accel, dt
            )
            if not result.is_safe:
                # Varsle kun ved tilstandsovergang eller når selve
                # bruddmengden endrer seg — ellers ville en konstant
                # bruddtilstand spamme signal-køen 50 Hz.
                violations_now = list(result.violations)
                if (
                    self._previous_safety_safe
                    or violations_now != self._last_safety_violations
                ):
                    self._notify_safety_violations(result.severity, violations_now)
                    self._last_safety_violations = violations_now
                self._previous_safety_safe = False
                if result.severity is SafetySeverity.CRITICAL:
                    self.emergency_stop()
                    return
                if result.severity is SafetySeverity.ERROR:
                    return
                # WARNING: la kommandoen gå gjennom, lytteren har fått varselet.
            else:
                # Tilbake til safe — nullstill slik at neste brudd igjen
                # blir sett som en kantovergang.
                self._previous_safety_safe = True
                self._last_safety_violations = []

        # 6: Sett servovinkler
        if self._servo_array is not None:
            self._servo_array.set_angles(angles)

    @property
    def target_pose(self) -> Pose:
        """Hent navaerende mal-pose.

        Returns:
            Mal-posen som kontrolleren styrer mot.
        """
        with self._lock:
            return self._target_pose

    @property
    def pose_controller(self) -> PoseController | None:
        """Hent PoseController-instansen for PID-tuning via GUI.

        Returns:
            PoseController eller None hvis ikke initialisert.
        """
        return self._pose_controller

    @property
    def safety_monitor(self) -> SafetyMonitor | None:
        """Hent SafetyMonitor-instansen for GUI-tilgang.

        Returns:
            SafetyMonitor eller None hvis ikke initialisert.
        """
        return self._safety_monitor

    @property
    def imu_fusion(self) -> IMUFusion | None:
        """Hent IMUFusion-instansen for GUI-tilgang.

        Returns:
            IMUFusion eller None hvis ikke initialisert.
        """
        return self._imu_fusion

    @property
    def base_imu(self) -> IMUInterface | None:
        """Hent bunnplate-IMU (LSM6DSOXTR) for GUI-avlesning.

        Returns:
            IMUInterface eller None hvis ikke initialisert.
        """
        return self._base_imu

    @property
    def servo_array(self) -> ServoArray | None:
        """Hent ServoArray-instansen for GUI-tilgang.

        Returns:
            ServoArray eller None hvis ikke initialisert.
        """
        return self._servo_array

    def get_current_pose(self) -> Pose:
        """Hent estimert orientering for bunnplaten.

        Returns:
            Estimert 6-DOF pose basert på bunnplate-IMU-fusjon.
        """
        with self._lock:
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

    def get_imu_snapshot(self) -> tuple[Vector3, Vector3, Vector3]:
        """Hent siste IMU-verdier (accel, gyro, orientering).

        Når kontroll-tråden kjører returneres cachet verdier som
        step() oppdaterer 50 Hz — slik unngår vi I2C-konkurranse.

        Når kontroll-tråden står stille (før operatøren har trykket
        Start) leses IMU direkte og cachen oppdateres. Uten dette
        ville GUI-grafer vise en flatlinje på siste pre-fyllte verdi
        helt til Start trykkes. Det er trygt fordi det da ikke er
        noen annen tråd som rører I2C-bussen.
        """
        if self.is_running() or self._base_imu is None:
            with self._lock:
                return self._last_accel, self._last_gyro, self._last_orientation

        accel = self._base_imu.read_acceleration()
        gyro = self._base_imu.read_angular_velocity()
        if self._imu_fusion is not None:
            orient = self._imu_fusion.update(accel, gyro, 1.0 / self._loop_rate_hz)
        else:
            orient = Vector3(0.0, 0.0, 0.0)
        # Oppdater også current_pose slik at PID-feilgrafen i pid-tab
        # viser ekte feil mot mål-pose før Start, og ikke bare null.
        new_current = Pose(rotation=orient)
        with self._lock:
            self._last_accel = accel
            self._last_gyro = gyro
            self._last_orientation = orient
            self._current_pose = new_current
        return accel, gyro, orient

    def is_running(self) -> bool:
        """Sjekk om kontrollsløyfen kjører.

        Returns:
            True hvis det finnes en levende kontroll-tråd.
        """
        return self._thread is not None and self._thread.is_alive()

    def shutdown(self) -> None:
        """Sikker avslutning av hele systemet.

        Stopper kontrollsløyfen, frikoblet alle servoer og
        lukker I2C-forbindelsen. Idempotent — trygg å kalle
        flere ganger.
        """
        self.stop()
        if self._servo_array is not None:
            self._servo_array.detach_all()
        self._servo_array = None
        self._base_imu = None
        self._ik_solver = None
        self._pose_controller = None
        self._imu_fusion = None
        self._safety_monitor = None
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                # Lukking skal aldri felle nedstegningen — logg men gå videre.
                pass
            self._bus = None

    # -----------------------------------------------------------------
    # Sikkerhetsvarsler
    # -----------------------------------------------------------------

    def add_safety_listener(self, listener: SafetyViolationListener) -> None:
        """Registrer en lytter for sikkerhetsbrudd fra step()-løkken.

        Lytteren kalles med (severity, violations) hver gang
        check_all rapporterer brudd. Brukes typisk av GUI for å
        vise brudd i status-banner og event-log.

        Args:
            listener: Funksjon som tar (SafetySeverity, list[str]).
        """
        self._safety_listeners.append(listener)

    def remove_safety_listener(self, listener: SafetyViolationListener) -> None:
        """Fjern en tidligere registrert sikkerhetslytter.

        Args:
            listener: Lytteren som skal fjernes.

        Raises:
            ValueError: Hvis lytteren ikke er registrert.
        """
        self._safety_listeners.remove(listener)

    def _notify_safety_violations(
        self,
        severity: SafetySeverity,
        violations: List[str],
    ) -> None:
        """Varsle alle registrerte lyttere om et sikkerhetsbrudd."""
        for listener in self._safety_listeners:
            try:
                listener(severity, violations)
            except Exception:
                # En dårlig lytter skal ikke felle kontroll-løkka.
                pass

    # -----------------------------------------------------------------
    # Loop-feil
    # -----------------------------------------------------------------

    def add_loop_error_listener(self, listener: LoopErrorListener) -> None:
        """Registrer en lytter som kalles ved uventet feil i kontroll-tråden.

        Brukes typisk av GUI for å vise at kontroll-løkka har
        kræsjet — uten dette ville feilen bare ført til at tråden
        forsvant uten varsel.

        Args:
            listener: Callback som tar selve exception-objektet.
        """
        self._error_listeners.append(listener)

    def remove_loop_error_listener(self, listener: LoopErrorListener) -> None:
        """Fjern en tidligere registrert loop-feilslytter."""
        self._error_listeners.remove(listener)

    def _notify_loop_error(self, exc: BaseException) -> None:
        """Varsle alle registrerte loop-feilslyttere."""
        for listener in self._error_listeners:
            try:
                listener(exc)
            except Exception:
                pass
