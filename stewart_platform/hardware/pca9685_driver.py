# pca9685_driver.py
# =================
# Driver for PCA9685 16-kanals PWM-kontroller over I2C.
# Brukes til å styre de 6 servomotorene på Stewart-plattformen.
# PWM-frekvens og I2C-adresse er konfigurerbare.

from __future__ import annotations

import time

from .i2c_bus import I2CBus


# Register-adresser (fra PCA9685-databladet)
_MODE1 = 0x00
_MODE2 = 0x01
_LED0_ON_L = 0x06          # Kanal n bruker 0x06 + 4*n .. 0x09 + 4*n
_ALL_LED_ON_L = 0xFA       # Skriver til alle 16 kanaler samtidig
_PRE_SCALE = 0xFE

# MODE1-bits
_MODE1_RESTART = 0x80
_MODE1_AI = 0x20           # Auto-increment — kreves for blokk-skriving
_MODE1_SLEEP = 0x10

# MODE2-bits
_MODE2_OUTDRV = 0x04       # Totem-pole-utgang (servoer trenger dette)

# Klokkefrekvens og PWM-oppløsning
_OSCILLATOR_HZ = 25_000_000
_PWM_RESOLUTION = 4096     # 12-bits oppløsning


class PCA9685Driver:
    """Driver for PCA9685 PWM-kontroller.

    PCA9685 er en 16-kanals, 12-bits PWM-driver som kommuniserer
    over I2C. Den genererer PWM-signaler for å styre servomotorer.
    Hver kanal kan settes individuelt med presisjon på 4096 trinn.

    Typisk bruk for servoer:
    - Frekvens: 50 Hz (20 ms periode)
    - Pulsbredde: 500-2500 µs avhengig av servo
    """

    def __init__(self, bus: I2CBus, address: int, frequency: int) -> None:
        """Opprett en ny PCA9685-driver.

        Args:
            bus: I2C-bussinstans for kommunikasjon.
            address: I2C-adresse for PCA9685 (standard: 0x40).
            frequency: PWM-frekvens i Hz (standard: 50 for servoer).
        """
        self._bus = bus
        self._address = address
        self._frequency = frequency

    def reset(self) -> None:
        """Tilbakestill PCA9685 til standardinnstillinger.

        Setter alle kanaler til 0 og konfigurerer standardregistre.
        Bør kalles ved oppstart.
        """
        # Sove først så frekvens kan settes trygt; OUTDRV må til for servoer.
        self._bus.write_byte_data(self._address, _MODE1, _MODE1_SLEEP)
        self._bus.write_byte_data(self._address, _MODE2, _MODE2_OUTDRV)
        # AI på, ut av sleep — kreves for at write_block_data skal nå alle 4 LED-registre.
        self._bus.write_byte_data(self._address, _MODE1, _MODE1_AI)
        time.sleep(0.001)  # oscillator-oppstart
        self.set_all_pwm(0, 0)
        self.set_frequency(self._frequency)

    def set_frequency(self, freq_hz: int) -> None:
        """Sett PWM-frekvensen for alle kanaler.

        Frekvensen beregnes via prescale-registeret.
        For servoer er 50 Hz standard (20 ms periode).

        Args:
            freq_hz: Ønsket frekvens i Hz (typisk 50 for servoer).
        """
        prescale = int(round(_OSCILLATOR_HZ / (_PWM_RESOLUTION * freq_hz))) - 1
        if not 3 <= prescale <= 255:
            raise ValueError(
                f"Frekvens {freq_hz} Hz gir ugyldig prescale {prescale} (må være 3..255)."
            )

        # PCA9685 krever sleep-modus for å skrive PRE_SCALE.
        old_mode = self._bus.read_byte_data(self._address, _MODE1)
        sleep_mode = (old_mode & ~_MODE1_RESTART) | _MODE1_SLEEP
        self._bus.write_byte_data(self._address, _MODE1, sleep_mode)
        self._bus.write_byte_data(self._address, _PRE_SCALE, prescale)
        self._bus.write_byte_data(self._address, _MODE1, old_mode)
        time.sleep(0.001)
        self._bus.write_byte_data(self._address, _MODE1, old_mode | _MODE1_RESTART)

        self._frequency = freq_hz

    def set_pwm(self, channel: int, on_tick: int, off_tick: int) -> None:
        """Sett PWM for en kanal med rå tick-verdier.

        PCA9685 bruker 12-bits oppløsning (0-4095 ticks per periode).

        Args:
            channel: PWM-kanal (0-15).
            on_tick: Tick-verdi der signalet går høyt (0-4095).
            off_tick: Tick-verdi der signalet går lavt (0-4095).
        """
        if not 0 <= channel < 16:
            raise ValueError(f"Kanal {channel} utenfor område 0..15.")
        on_tick = max(0, min(_PWM_RESOLUTION - 1, on_tick))
        off_tick = max(0, min(_PWM_RESOLUTION - 1, off_tick))

        base = _LED0_ON_L + 4 * channel
        self._bus.write_block_data(
            self._address,
            base,
            [
                on_tick & 0xFF,
                (on_tick >> 8) & 0x0F,
                off_tick & 0xFF,
                (off_tick >> 8) & 0x0F,
            ],
        )

    def set_pulse_width_us(self, channel: int, pulse_us: int) -> None:
        """Sett pulsbredde i mikrosekunder for en kanal.

        Bekvemmelighetsmetode som konverterer mikrosekunder til
        tick-verdier basert på gjeldende frekvens. Dette er den
        foretrukne metoden for servostyring.

        Args:
            channel: PWM-kanal (0-15).
            pulse_us: Pulsbredde i mikrosekunder (typisk 500-2500).
        """
        period_us = 1_000_000 / self._frequency
        off_tick = int(round(pulse_us * _PWM_RESOLUTION / period_us))
        self.set_pwm(channel, 0, off_tick)

    def set_all_pwm(self, on_tick: int, off_tick: int) -> None:
        """Sett samme PWM-verdier for alle 16 kanaler samtidig.

        Nyttig for å slå av alle servoer eller sette en felles
        nøytralposisjon.

        Args:
            on_tick: Tick-verdi der signalet går høyt.
            off_tick: Tick-verdi der signalet går lavt.
        """
        on_tick = max(0, min(_PWM_RESOLUTION - 1, on_tick))
        off_tick = max(0, min(_PWM_RESOLUTION - 1, off_tick))
        self._bus.write_block_data(
            self._address,
            _ALL_LED_ON_L,
            [
                on_tick & 0xFF,
                (on_tick >> 8) & 0x0F,
                off_tick & 0xFF,
                (off_tick >> 8) & 0x0F,
            ],
        )

    def sleep(self) -> None:
        """Sett PCA9685 i lavstrømsmodus.

        Stopper alle PWM-signaler. Bruk wake() for å gjenoppta.
        """
        mode = self._bus.read_byte_data(self._address, _MODE1)
        self._bus.write_byte_data(self._address, _MODE1, mode | _MODE1_SLEEP)

    def wake(self) -> None:
        """Vekk PCA9685 fra lavstrømsmodus og gjenoppta PWM-signaler."""
        mode = self._bus.read_byte_data(self._address, _MODE1)
        awake = mode & ~_MODE1_SLEEP
        self._bus.write_byte_data(self._address, _MODE1, awake)
        time.sleep(0.001)
        self._bus.write_byte_data(self._address, _MODE1, awake | _MODE1_RESTART)
