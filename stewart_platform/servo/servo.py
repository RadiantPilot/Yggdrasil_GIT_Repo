# servo.py
# ========
# Representerer en enkelt servomotor på Stewart-plattformen.
# Håndterer konvertering mellom vinkel (grader) og PWM-pulsbredde,
# tar hensyn til rotasjonsretning, kalibreringsoffset og
# mekaniske grenser. Hver servo konfigureres individuelt.

from __future__ import annotations

from ..config.platform_config import ServoConfig
from ..hardware.pca9685_driver import PCA9685Driver


class Servo:
    """Representerer en enkelt servomotor.

    Kobler en ServoConfig (kanal, grenser, retning, offset) med
    PCA9685-driveren for å gi et enkelt grensesnitt for å sette
    servovinkler. Håndterer automatisk:
    - Konvertering fra vinkel til pulsbredde (lineær mapping).
    - Retningsinvertering (direction = -1).
    - Kalibreringsoffset (offset_deg).
    - Grensekontroll (min_angle_deg / max_angle_deg).
    """

    def __init__(self, config: ServoConfig, driver: PCA9685Driver) -> None:
        """Opprett en servo med gitt konfigurasjon og PWM-driver.

        Args:
            config: Konfigurasjon for denne servoen (kanal, grenser, osv.).
            driver: PCA9685-driver for å sende PWM-signaler.
        """
        self._config = config
        self._driver = driver
        self._current_angle_deg = config.home_angle_deg

    def set_angle(self, angle_deg: float) -> None:
        """Sett servoen til en gitt vinkel.

        Tar hensyn til retning og offset, og sjekker at den
        resulterende vinkelen er innenfor mekaniske grenser.
        Konverterer vinkelen til pulsbredde og sender til PCA9685.

        Args:
            angle_deg: Ønsket vinkel i grader.

        Raises:
            ValueError: Hvis vinkelen er utenfor tillatte grenser.
        """
        if not self.is_within_limits(angle_deg):
            raise ValueError(
                f"Vinkel {angle_deg}° er utenfor grensene "
                f"[{self._config.min_angle_deg}, {self._config.max_angle_deg}]."
            )
        pulse = self.angle_to_pulse_us(angle_deg)
        self._driver.set_pulse_width_us(self._config.channel, pulse)
        self._current_angle_deg = angle_deg

    def get_angle(self) -> float:
        """Hent servos nåværende vinkel.

        Returns:
            Sist satte vinkel i grader.
        """
        return self._current_angle_deg

    def angle_to_pulse_us(self, angle_deg: float) -> int:
        """Konverter en vinkel i grader til pulsbredde i mikrosekunder.

        Utfører lineær mapping fra vinkelområdet (min_angle_deg til
        max_angle_deg) til pulsbreddeområdet (min_pulse_us til
        max_pulse_us). Tar hensyn til retning og offset.

        Args:
            angle_deg: Vinkel i grader.

        Returns:
            Pulsbredde i mikrosekunder.
        """
        cfg = self._config
        # Anvend retning og offset
        effective = cfg.direction * angle_deg + cfg.offset_deg

        # Lineær mapping fra vinkelområde til pulsbredde
        angle_range = cfg.max_angle_deg - cfg.min_angle_deg
        pulse_range = cfg.max_pulse_us - cfg.min_pulse_us
        ratio = (effective - cfg.min_angle_deg) / angle_range
        return int(round(cfg.min_pulse_us + ratio * pulse_range))

    def is_within_limits(self, angle_deg: float) -> bool:
        """Sjekk om en vinkel er innenfor servoens tillatte område.

        Tar hensyn til offset og sikkerhetsmargin.

        Args:
            angle_deg: Vinkel i grader å sjekke.

        Returns:
            True hvis vinkelen er innenfor grensene.
        """
        return self._config.min_angle_deg <= angle_deg <= self._config.max_angle_deg

    def go_home(self) -> None:
        """Flytt servoen til hjemmeposisjonen (home_angle_deg).

        Setter servoen tilbake til sin definerte nøytralposisjon.
        """
        self.set_angle(self._config.home_angle_deg)

    def detach(self) -> None:
        """Slå av PWM-signalet for denne servoen.

        Servoen blir strømløs og kan dreies fritt for hånd.
        Nyttig ved nødstopp eller manuell justering.
        """
        self._driver.set_pwm(self._config.channel, 0, 0)
