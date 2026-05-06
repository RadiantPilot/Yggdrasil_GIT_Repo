# test_servo_sweep.py
# ===================
# Interaktiv test for enkeltservobevegelse.
# Brukeren velger servo (1–6), og servoen beveger seg jevnt fra bunn-
# posisjon til toppposisjon og tilbake til midtstilling, basert på
# verdiene i default_config.yaml.
#
# Kjøres på Pi:
#     python scripts/test_servo_sweep.py
#     python scripts/test_servo_sweep.py --speed 60   # grader per sekund

from __future__ import annotations

import argparse
import sys
import time

from stewart_platform.config.platform_config import PlatformConfig
from stewart_platform.hardware.i2c_bus import I2CBus
from stewart_platform.hardware.pca9685_driver import PCA9685Driver
from stewart_platform.servo.servo import Servo

CONFIG_PATH = "config/default_config.yaml"
STEP_INTERVAL_S = 0.02          # 50 Hz oppdateringsrate under sweep
DEFAULT_SPEED_DEG_S = 90.0      # grader per sekund


def _sweep(servo: Servo, from_deg: float, to_deg: float, speed_deg_s: float) -> None:
    """Flytt servoen jevnt fra from_deg til to_deg med gitt hastighet."""
    step = STEP_INTERVAL_S * speed_deg_s
    current = from_deg
    direction = 1.0 if to_deg > from_deg else -1.0

    while direction * (to_deg - current) > 0:
        current += direction * step
        # Klem til målvinkelen så vi ikke overskyter
        if direction * (current - to_deg) > 0:
            current = to_deg
        servo.set_angle(current)
        time.sleep(STEP_INTERVAL_S)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interaktiv servo-sweep: bunn → topp → midt.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=DEFAULT_SPEED_DEG_S,
        metavar="DEG_S",
        help=f"Bevegelseshastighet i grader per sekund (default {DEFAULT_SPEED_DEG_S}).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    speed = args.speed

    cfg = PlatformConfig.load(CONFIG_PATH)

    bus = I2CBus(cfg.i2c_bus_number)
    pca = PCA9685Driver(bus, address=cfg.pca9685_address, frequency=cfg.pca9685_frequency)
    pca.reset()
    time.sleep(0.02)

    servos = [Servo(sc, pca) for sc in cfg.servo_configs]

    print("Stewart Platform — interaktiv servo-sweep")
    print(f"Hastighet: {speed:.0f} °/s  |  Trykk Ctrl+C for å avslutte\n")

    try:
        while True:
            raw = input("Velg servo (1–6): ").strip()
            if not raw:
                continue
            try:
                nummer = int(raw)
            except ValueError:
                print("  Ugyldig input — skriv et tall mellom 1 og 6.")
                continue
            if not 1 <= nummer <= 6:
                print("  Tallet må være mellom 1 og 6.")
                continue

            idx = nummer - 1
            servo = servos[idx]
            sc = cfg.servo_configs[idx]

            bunn = sc.min_angle_deg
            topp = sc.max_angle_deg
            midt = sc.home_angle_deg

            print(f"  Servo {nummer} (kanal {sc.channel}): "
                  f"bunn={bunn:.0f}° → topp={topp:.0f}° → midt={midt:.0f}°")

            # Start fra bunn
            print(f"    Går til bunn ({bunn:.0f}°) ...")
            _sweep(servo, servo.get_angle(), bunn, speed)

            # Sweep til topp
            print(f"    Sweep til topp ({topp:.0f}°) ...")
            _sweep(servo, bunn, topp, speed)

            # Tilbake til midtstilling
            print(f"    Tilbake til midt ({midt:.0f}°) ...")
            _sweep(servo, topp, midt, speed)
            print("    Ferdig.\n")

    except KeyboardInterrupt:
        print("\nAvbrutt av bruker.")
    finally:
        print("Slår av PWM på alle kanaler...")
        pca.set_all_pwm(0, 0)
        bus.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
