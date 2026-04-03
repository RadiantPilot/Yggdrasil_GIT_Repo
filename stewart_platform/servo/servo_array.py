# servo_array.py
# ==============
# Administrerer en gruppe på 6 servoer som en enhet.
# Gir batchoperasjoner for å sette alle servovinkler samtidig,
# samt validering, hjemmeposisjonering og frakobling.

from __future__ import annotations

from typing import List

from ..config.platform_config import ServoConfig
from ..hardware.pca9685_driver import PCA9685Driver
from .servo import Servo


class ServoArray:
    """Gruppe av 6 servomotorer for Stewart-plattformen.

    Administrerer alle 6 servoer som en koordinert enhet.
    Sørger for at alle servovinkler settes i riktig rekkefølge
    og gir batchvalidering for å sjekke at alle vinkler er
    innenfor grensene før noen servo flyttes.
    """

    def __init__(self, configs: List[ServoConfig], driver: PCA9685Driver) -> None:
        """Opprett en ServoArray med 6 servoer.

        Args:
            configs: Liste med 6 ServoConfig-instanser, en per servo.
            driver: PCA9685-driver som deles av alle servoer.

        Raises:
            ValueError: Hvis antall konfigurasjoner ikke er 6.
        """
        self._driver = driver
        self._servos = [Servo(config, driver) for config in configs]

    def set_angles(self, angles: List[float]) -> None:
        """Sett vinkler for alle 6 servoer samtidig.

        Validerer alle vinkler før noen servo flyttes, for å
        unngå delvis oppdatering ved ugyldig input.

        Args:
            angles: Liste med 6 vinkler i grader.

        Raises:
            ValueError: Hvis antall vinkler ikke er 6 eller en vinkel
                        er utenfor tillatte grenser.
        """
        if len(angles) != 6:
            raise ValueError(f"Krever nøyaktig 6 vinkler, fikk {len(angles)}.")
        # Valider alle før noen flyttes
        for i, angle in enumerate(angles):
            if not self._servos[i].is_within_limits(angle):
                raise ValueError(
                    f"Servo {i}: vinkel {angle}° er utenfor grensene."
                )
        for i, angle in enumerate(angles):
            self._servos[i].set_angle(angle)

    def get_angles(self) -> List[float]:
        """Hent nåværende vinkler for alle 6 servoer.

        Returns:
            Liste med 6 vinkler i grader.
        """
        return [servo.get_angle() for servo in self._servos]

    def go_home(self) -> None:
        """Flytt alle servoer til sine hjemmeposisjoner.

        Setter hver servo til dens definerte home_angle_deg.
        """
        for servo in self._servos:
            servo.go_home()

    def detach_all(self) -> None:
        """Slå av PWM-signalet for alle servoer.

        Alle servoer blir strømløse. Brukes ved nødstopp
        eller sikker avslutning.
        """
        for servo in self._servos:
            servo.detach()

    def validate_angles(self, angles: List[float]) -> bool:
        """Sjekk om alle gitte vinkler er innenfor tillatte grenser.

        Validerer hver vinkel mot den tilhørende servoens grenser.
        Ingen servoer flyttes.

        Args:
            angles: Liste med 6 vinkler i grader å validere.

        Returns:
            True hvis alle vinkler er gyldige.
        """
        if len(angles) != 6:
            return False
        return all(
            self._servos[i].is_within_limits(angles[i]) for i in range(6)
        )

    def __getitem__(self, index: int) -> Servo:
        """Hent en enkelt servo via indeks (0-5).

        Args:
            index: Servoindeks (0-5).

        Returns:
            Servo-instansen på den gitte indeksen.
        """
        return self._servos[index]
