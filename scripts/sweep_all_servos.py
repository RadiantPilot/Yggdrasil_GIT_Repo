# sweep_all_servos.py
# ===================
# Enkel PWM-feilsøking: beveger alle 6 servoer fram og tilbake mellom to
# pulsbredder, gjentatte ganger, helt til brukeren stopper med Ctrl+C.
#
# Ingen prompts, ingen kinematikk, ingen config-lasting — bare rå PWM
# rett på PCA9685. Brukes til å bekrefte at signalet kommer ut og
# servoene reagerer.
#
# Kjøres på Pi:
#     python scripts/sweep_all_servos.py
#     python scripts/sweep_all_servos.py --min 1200 --max 1800
#     python scripts/sweep_all_servos.py --period 2.0
#     python scripts/sweep_all_servos.py --channels 0 1 2

from __future__ import annotations

import argparse
import sys
import time

from stewart_platform.hardware.i2c_bus import I2CBus
from stewart_platform.hardware.pca9685_driver import PCA9685Driver

I2C_BUS_NUMBER = 1
PCA_ADDRESS = 0x40
PWM_FREQUENCY_HZ = 50

DEFAULT_CHANNELS = (0, 1, 2, 3, 4, 5)
DEFAULT_PULSE_MIN_US = 1300
DEFAULT_PULSE_MAX_US = 1700
DEFAULT_HALF_PERIOD_S = 1.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweeper alle servoer fram og tilbake for PWM-feilsøking.",
    )
    parser.add_argument(
        "--channels",
        type=int,
        nargs="+",
        default=list(DEFAULT_CHANNELS),
        choices=range(16),
        metavar="N",
        help="Kanaler å sweepe (default 0 1 2 3 4 5).",
    )
    parser.add_argument(
        "--min",
        dest="pulse_min",
        type=int,
        default=DEFAULT_PULSE_MIN_US,
        help=f"Nedre pulsbredde i µs (default {DEFAULT_PULSE_MIN_US}).",
    )
    parser.add_argument(
        "--max",
        dest="pulse_max",
        type=int,
        default=DEFAULT_PULSE_MAX_US,
        help=f"Øvre pulsbredde i µs (default {DEFAULT_PULSE_MAX_US}).",
    )
    parser.add_argument(
        "--period",
        type=float,
        default=2 * DEFAULT_HALF_PERIOD_S,
        help="Full sweep-periode i sekunder (fram + tilbake, default 2.0).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    channels = list(args.channels)
    pulse_min = args.pulse_min
    pulse_max = args.pulse_max
    half_period = max(args.period / 2.0, 0.05)

    if pulse_min >= pulse_max:
        print(f"FEIL: --min ({pulse_min}) må være mindre enn --max ({pulse_max}).")
        return 2

    bus = I2CBus(I2C_BUS_NUMBER)
    pca = PCA9685Driver(bus, address=PCA_ADDRESS, frequency=PWM_FREQUENCY_HZ)

    print(f"Initialiserer PCA9685 på 0x{PCA_ADDRESS:02X} med {PWM_FREQUENCY_HZ} Hz...")
    pca.reset()
    time.sleep(0.01)

    print(f"Sweeper kanaler {channels} mellom {pulse_min} µs og {pulse_max} µs")
    print(f"Halv periode = {half_period:.2f} s. Trykk Ctrl+C for å stoppe.\n")

    pulse_now = pulse_min
    pulse_next = pulse_max
    iteration = 0

    try:
        while True:
            iteration += 1
            print(f"  [{iteration:4d}] -> {pulse_now} µs")
            for channel in channels:
                pca.set_pulse_width_us(channel, pulse_now)
            time.sleep(half_period)
            pulse_now, pulse_next = pulse_next, pulse_now
    except KeyboardInterrupt:
        print("\nAvbrutt av bruker.")
    finally:
        print("Slår av PWM på alle kanaler...")
        pca.set_all_pwm(0, 0)
        bus.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
