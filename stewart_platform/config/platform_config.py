# platform_config.py
# ===================
# Sentral konfigurasjonsfil for Stewart-plattformen.
# Alle justerbare parametere er samlet her slik at man kan
# endre oppførsel via en YAML-fil uten å røre koden.

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import List, Optional

import yaml

from .button_config import ButtonConfig


class Axis(IntEnum):
    """Rotasjonsakser for Stewart-plattformen.

    Plattformen styres kun rotasjonelt (translasjon er fjernet).
    Brukes for per-akse PID-tuning og GUI-navigasjon.
    """
    ROLL = 0
    PITCH = 1
    YAW = 2


@dataclass
class ServoConfig:
    """Konfigurasjon for en enkelt servomotor.

    Hver servo har sin egen kanal, pulsbredde-område, vinkelgrenser,
    rotasjonsretning og kalibreringsoffset. Dette gjør det enkelt å
    justere hver servo individuelt etter montering.
    """

    # PCA9685-kanal (0-15) som servoen er koblet til.
    channel: int = 0

    # Minimum pulsbredde i mikrosekunder. Tilsvarer min_angle_deg.
    min_pulse_us: int = 500

    # Maksimum pulsbredde i mikrosekunder. Tilsvarer max_angle_deg.
    max_pulse_us: int = 2500

    # Minimum tillatt vinkel i grader (mekanisk grense).
    min_angle_deg: float = 0.0

    # Maksimum tillatt vinkel i grader (mekanisk grense).
    max_angle_deg: float = 180.0

    # Nøytral vinkel i grader (hjemmeposisjon).
    home_angle_deg: float = 90.0

    # Rotasjonsretning: +1 for normal, -1 for invertert.
    direction: int = 1

    # Kalibreringsoffset i grader for å kompensere for monteringsfeil.
    offset_deg: float = 0.0

    # Servoens monteringsvinkel på bunnplaten i grader.
    mounting_angle_deg: float = 0.0


@dataclass
class PIDGains:
    """PID-regulatorforsterkning.

    Deles av alle tre rotasjonsakser ved opprettelse, men kan
    overstyres per akse via PoseController.set_pid_gains.

    output_min/output_max er per-tick korreksjon i grader.
    """

    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.0
    output_min: float = -10.0
    output_max: float = 10.0
    integral_limit: float = 100.0


@dataclass
class SafetyConfig:
    """Sikkerhetsgrenser for plattformen (kun rotasjon).

    Translasjon-grenser er fjernet — plattformen kan ikke lenger
    bevege seg lineært i denne modellen.
    """

    # Hvis False, hopper SafetyMonitor over alle sjekker. Brukes
    # under bringup/tuning. Slå PÅ igjen så snart plattformen er
    # trygg å kjøre med.
    enabled: bool = True

    # Maksimal rotasjon fra nøytral i grader.
    max_rotation_deg: float = 30.0

    # Maksimal vinkelhastighet i grader/s.
    max_angular_velocity_deg_per_s: float = 60.0

    # Sikkerhetsmargin for servovinkler i grader.
    servo_angle_margin_deg: float = 5.0

    # Watchdog-tidsgrense i sekunder.
    watchdog_timeout_s: float = 1.0

    # Terskel for IMU-feildeteksjon i g.
    imu_fault_threshold_g: float = 4.0


@dataclass
class PlatformConfig:
    """Hovedkonfigurasjon for hele Stewart-plattformen.

    Samler alle parametere som trengs for å styre plattformen:
    I2C-adresser, geometri, servokonfigurasjon, PID-forsterkning
    og sikkerhetsgrenser. Kan lastes fra og lagres til YAML-fil.
    """

    # --- I2C-innstillinger ---

    # I2C-bussnummer på Raspberry Pi (vanligvis 1).
    i2c_bus_number: int = 1

    # I2C-adresse for PCA9685 PWM-driver.
    pca9685_address: int = 0x40

    # PWM-frekvens for PCA9685 i Hz (50 Hz er standard for servoer).
    pca9685_frequency: int = 50

    # I2C-adresse for LSM6DSOXTR IMU på bunnplaten.
    lsm6dsox_address: int = 0x6A

    # --- Plattformgeometri ---

    # Radius for bunnplaten i millimeter (senter til leddpunkt).
    base_radius: float = 100.0

    # Radius for toppplaten i millimeter (senter til leddpunkt).
    platform_radius: float = 75.0

    # Vinkler for de 6 leddpunktene på bunnplaten i grader.
    base_joint_angles: List[float] = field(
        default_factory=lambda: [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]
    )

    # Vinkler for de 6 leddpunktene på toppplaten i grader.
    platform_joint_angles: List[float] = field(
        default_factory=lambda: [30.0, 90.0, 150.0, 210.0, 270.0, 330.0]
    )

    # Lengde på servoarmen (horn) i millimeter.
    servo_horn_length: float = 25.0

    # Lengde på forbindelsesstagen mellom servoarm og toppplate i millimeter.
    rod_length: float = 150.0

    # Hvilehøyde for toppplaten over bunnplaten i millimeter.
    # Brukes som fast translasjon-Z i kinematikken — toppplaten
    # holder samme høyde i alle stillinger og roterer kun.
    # Kan settes til None i YAML for å la PlatformGeometry beregne
    # høyden geometrisk (sqrt(rod_length^2 - horisontalt^2)).
    home_height: Optional[float] = 120.0

    # --- Servo-, PID- og sikkerhetsinnstillinger ---

    # Konfigurasjon for de 6 servomotorene.
    servo_configs: List[ServoConfig] = field(
        default_factory=lambda: [ServoConfig(channel=i) for i in range(6)]
    )

    # PID-regulatorforsterkning.
    pid_gains: PIDGains = field(default_factory=PIDGains)

    # Frekvens for kontrollsløyfen i Hz.
    control_loop_rate_hz: float = 50.0

    # Sikkerhetsgrenser.
    safety_config: SafetyConfig = field(default_factory=SafetyConfig)

    # Konfigurasjon for det fysiske knappekortet (5-knappers
    # navigasjon). Kan deaktiveres ved å sette enabled: false.
    button_config: ButtonConfig = field(default_factory=ButtonConfig)

    @classmethod
    def load(cls, filepath: str) -> PlatformConfig:
        """Last konfigurasjon fra en YAML-fil.

        Leser en YAML-fil og oppretter en PlatformConfig-instans
        med verdiene fra filen. Felter som ikke er spesifisert i
        filen beholder sine standardverdier.

        Args:
            filepath: Sti til YAML-konfigurasjonsfilen.

        Returns:
            En PlatformConfig-instans med innlastede verdier.

        Raises:
            FileNotFoundError: Hvis filen ikke finnes.
            ValueError: Hvis filen inneholder ugyldige verdier.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Konfigurasjonsfil ikke funnet: {filepath}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError(f"Tom eller ugyldig YAML-fil: {filepath}")

        # Bygg nestede dataklasser fra YAML-data
        servo_configs_data = data.pop("servo_configs", None)
        pid_gains_data = data.pop("pid_gains", None)
        safety_config_data = data.pop("safety_config", None)
        button_config_data = data.pop("button_config", None)

        config = cls(**data)

        if servo_configs_data is not None:
            config.servo_configs = [
                ServoConfig(**s) for s in servo_configs_data
            ]
        if pid_gains_data is not None:
            config.pid_gains = PIDGains(**pid_gains_data)
        if safety_config_data is not None:
            config.safety_config = SafetyConfig(**safety_config_data)
        if button_config_data is not None:
            config.button_config = ButtonConfig(**button_config_data)

        return config

    def save(self, filepath: str) -> None:
        """Lagre konfigurasjon til en YAML-fil.

        Skriver alle konfigurasjonsparametere til en YAML-fil
        som kan redigeres manuelt og lastes inn igjen senere.

        Args:
            filepath: Sti til YAML-filen som skal skrives.
        """
        data = asdict(self)
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def validate(self) -> List[str]:
        """Valider at konfigurasjonen er konsistent og fysisk mulig.

        Samler alle valideringsfeil i en liste slik at GUI-en
        kan vise alle problemer samtidig.

        Sjekker blant annet at:
        - Det er nøyaktig 6 servokonfigurasjoner.
        - Vinkelgrenser er gyldige (min < max).
        - Geometriske dimensjoner er positive.

        Returns:
            Tom liste hvis alt er gyldig, ellers liste med feilmeldinger.
        """
        errors: List[str] = []

        if len(self.servo_configs) != 6:
            errors.append(
                f"Krever nøyaktig 6 servokonfigurasjoner, fikk {len(self.servo_configs)}."
            )

        for i, sc in enumerate(self.servo_configs):
            if sc.min_angle_deg >= sc.max_angle_deg:
                errors.append(
                    f"Servo {i}: min_angle_deg ({sc.min_angle_deg}) må være "
                    f"mindre enn max_angle_deg ({sc.max_angle_deg})."
                )

        if self.base_radius <= 0:
            errors.append(f"base_radius må være positiv, fikk {self.base_radius}.")
        if self.platform_radius <= 0:
            errors.append(f"platform_radius må være positiv, fikk {self.platform_radius}.")
        if self.rod_length <= 0:
            errors.append(f"rod_length må være positiv, fikk {self.rod_length}.")
        # home_height er Optional — None betyr "avled fra geometri".
        # Bare valider hvis brukeren har satt en eksplisitt verdi.
        if self.home_height is not None and self.home_height <= 0:
            errors.append(f"home_height må være positiv, fikk {self.home_height}.")
        if self.servo_horn_length <= 0:
            errors.append(f"servo_horn_length må være positiv, fikk {self.servo_horn_length}.")

        return errors

    def raise_if_invalid(self) -> None:
        """Valider konfigurasjonen og kast exception ved feil.

        Wrapper rundt validate() for kode som forventer exception-basert
        feilhåndtering.

        Raises:
            ValueError: Hvis konfigurasjonen er ugyldig. Meldingen
                        inneholder alle valideringsfeil.
        """
        errors = self.validate()
        if errors:
            raise ValueError("\n".join(errors))
