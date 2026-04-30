# bringup_one_servo.py
# ====================
# Standalone hardware-bringup-test for én servo koblet til PCA9685.
# Sender forsiktige pulsbredder og venter på Enter mellom hvert steg, slik
# at brukeren kan stoppe med Ctrl+C dersom servoen oppfører seg uventet.
#
# Forutsetninger:
#  - Kun én servo (DF9GMS eller annen 9g mikro-servo) koblet til valgt kanal
#  - Servoen står fritt — ikke montert mekanisk
#  - V+ til PCA9685 har riktig spenning (5–6 V)
#
# Kjøres på Pi:
#     python scripts/bringup_one_servo.py             # default kanal 0
#     python scripts/bringup_one_servo.py -c 3        # kanal 3
#     python scripts/bringup_one_servo.py --channel 5 # kanal 5

from __future__ import annotations

import argparse
import sys
import time

from stewart_platform.hardware.i2c_bus import I2CBus
from stewart_platform.hardware.pca9685_driver import PCA9685Driver

I2C_BUS_NUMBER = 1
PCA_ADDRESS = 0x40
PWM_FREQUENCY_HZ = 50
DEFAULT_SERVO_CHANNEL = 0

# Konservative pulsbredder for første test. DF9GMS støtter typisk 500–2400 µs,
# men vi holder oss godt innenfor for å unngå at servoen slår mot mekaniske
# stopp før vi vet at retning og kalibrering stemmer.
PULSE_CENTER_US = 1500
PULSE_LEFT_US = 1300
PULSE_RIGHT_US = 1700
PULSE_WIDE_LEFT_US = 1100
PULSE_WIDE_RIGHT_US = 1900

SETTLE_TIME_S = 0.5


def _prompt(message: str) -> None:
    """Skriv en melding og vent på Enter (Ctrl+C avbryter)."""
    try:
        input(f"  >> {message} (Enter for å fortsette, Ctrl+C avbryter): ")
    except EOFError:
        pass


def _send_pulse(pca: PCA9685Driver, channel: int, pulse_us: int, label: str) -> None:
    print(f"\n  Sender {pulse_us} µs til kanal {channel} ({label})")
    pca.set_pulse_width_us(channel, pulse_us)
    time.sleep(SETTLE_TIME_S)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bringup-test for én servo koblet til PCA9685.",
    )
    parser.add_argument(
        "-c", "--channel",
        type=int,
        default=DEFAULT_SERVO_CHANNEL,
        choices=range(16),
        metavar="N",
        help="PCA9685-kanal å teste (0–15, default 0).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    channel = args.channel

    bus = I2CBus(I2C_BUS_NUMBER)
    pca = PCA9685Driver(bus, address=PCA_ADDRESS, frequency=PWM_FREQUENCY_HZ)

    print(f"Initialiserer PCA9685 på 0x{PCA_ADDRESS:02X} med "
          f"{PWM_FREQUENCY_HZ} Hz...")
    pca.reset()
    time.sleep(0.01)

    print(f"\nSjekkliste før vi sender pulser:")
    print(f"  - Kun én servo koblet til kanal {channel}")
    print(f"  - Servoen står fritt (ikke fast i mekanikk)")
    print(f"  - Spenning til V+ er 5–6 V")
    print(f"  - Du har strømforsyningen lett tilgjengelig for å kutte raskt")
    _prompt("Klar til å sende første puls?")

    try:
        # --- Steg 1: Midtstilling ---------------------------------------
        _send_pulse(pca, channel, PULSE_CENTER_US, "midt")
        _prompt("Stoppet servoen på midten?")

        # --- Steg 2: Liten venstre-sweep --------------------------------
        _send_pulse(pca, channel, PULSE_LEFT_US, "litt venstre")
        _prompt("Beveget den seg litt mot venstre?")

        # --- Steg 3: Liten høyre-sweep ----------------------------------
        _send_pulse(pca, channel, PULSE_RIGHT_US, "litt høyre")
        _prompt("Beveget den seg gjennom midt og videre til høyre?")

        # --- Steg 4: Tilbake til midt -----------------------------------
        _send_pulse(pca, channel, PULSE_CENTER_US, "midt")
        _prompt("Tilbake på midten?")

        # --- Steg 5 (valgfritt): Bredere sweep --------------------------
        try:
            choice = input("\n  Vil du teste bredere sweep "
                           f"({PULSE_WIDE_LEFT_US}–{PULSE_WIDE_RIGHT_US} µs)? "
                           "[j/N]: ").strip().lower()
        except EOFError:
            choice = "n"

        if choice in ("j", "y", "ja", "yes"):
            _send_pulse(pca, channel, PULSE_WIDE_LEFT_US, "bredt venstre")
            _prompt("Stoppet på en lengre venstre-posisjon?")
            _send_pulse(pca, channel, PULSE_WIDE_RIGHT_US, "bredt høyre")
            _prompt("Stoppet på en lengre høyre-posisjon?")
            _send_pulse(pca, channel, PULSE_CENTER_US, "midt")
            _prompt("Tilbake på midten?")

    finally:
        # Slå alltid av kanalen ved avslutning, også ved Ctrl+C eller feil.
        print(f"\nSlår av PWM på kanal {channel}...")
        pca.set_pwm(channel, 0, 0)
        bus.close()

    print("Ferdig — servo-styring fungerer fra PCA9685.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAvbrutt av bruker.")
        sys.exit(130)
