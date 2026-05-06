# home_all_servos.py
# ==================
# Vrir hver servo litt fram og tilbake (en om gangen) og setter dem
# deretter alle til hjemmeposisjon. Brukes som "warm-up" før hovedkoden
# startes, slik at alle servoer står i en kjent vinkel og PWM-signalet
# er aktivt på alle kanaler.
#
# Bruker Servo og ServoArray fra stewart_platform-pakken slik at
# konfigurasjonen (kanal, retning, offset, grenser, home-vinkel) leses
# rett fra config/default_config.yaml.
#
# Kjøres på Pi:
#     python scripts/home_all_servos.py
#     python scripts/home_all_servos.py --wiggle 10 --hold 0.4
#     python scripts/home_all_servos.py --config config/min_egen.yaml
#     python scripts/home_all_servos.py --no-detach   # behold drivkraft

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from stewart_platform.config.platform_config import PlatformConfig
from stewart_platform.hardware.i2c_bus import I2CBus
from stewart_platform.hardware.pca9685_driver import PCA9685Driver
from stewart_platform.servo.servo_array import ServoArray

DEFAULT_CONFIG_PATH = str(Path(__file__).parent.parent / "config" / "default_config.yaml")
DEFAULT_WIGGLE_DEG = 15.0
DEFAULT_HOLD_S = 0.3
DEFAULT_SETTLE_S = 0.4


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Vri hver servo litt fram og tilbake, og sett dem deretter "
            "i hjemmeposisjon."
        ),
    )
    parser.add_argument(
        "--config",
        type=str,
        default=DEFAULT_CONFIG_PATH,
        help=f"Sti til YAML-konfigurasjon (default {DEFAULT_CONFIG_PATH}).",
    )
    parser.add_argument(
        "--wiggle",
        type=float,
        default=DEFAULT_WIGGLE_DEG,
        help=(
            f"Hvor mange grader hver servo skal vrides på hver side av "
            f"home_angle (default {DEFAULT_WIGGLE_DEG}°)."
        ),
    )
    parser.add_argument(
        "--hold",
        type=float,
        default=DEFAULT_HOLD_S,
        help=(
            f"Tid å holde hver wiggle-stilling i sekunder "
            f"(default {DEFAULT_HOLD_S} s)."
        ),
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=DEFAULT_SETTLE_S,
        help=(
            f"Tid å vente etter siste hjemmeplassering før utgang "
            f"(default {DEFAULT_SETTLE_S} s)."
        ),
    )
    parser.add_argument(
        "--no-detach",
        action="store_true",
        help=(
            "Ikke kutt PWM på slutten — servoene holder hjemmeposisjon "
            "med drivkraft. Default er å frikoble alle kanaler."
        ),
    )
    return parser.parse_args()


def _safe_wiggle_targets(
    home_deg: float,
    wiggle_deg: float,
    min_deg: float,
    max_deg: float,
) -> tuple[float, float]:
    """Klemmer wiggle-mål til servoens tillatte område.

    Returnerer (lav, høy) vinkel klemmet til [min_deg, max_deg] slik
    at vi aldri ber servoen om en posisjon utenfor grensene fra
    config-en.
    """
    lo = max(min_deg, home_deg - wiggle_deg)
    hi = min(max_deg, home_deg + wiggle_deg)
    return lo, hi


def main() -> int:
    args = _parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"FEIL: konfigurasjonsfil ikke funnet: {config_path}",
              file=sys.stderr)
        return 2

    print(f"Laster konfigurasjon fra {config_path}")
    cfg = PlatformConfig.load(str(config_path))
    errors = cfg.validate()
    if errors:
        print("FEIL i konfigurasjon:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 2

    bus = I2CBus(cfg.i2c_bus_number)
    driver = PCA9685Driver(bus, cfg.pca9685_address, cfg.pca9685_frequency)

    print(
        f"Initialiserer PCA9685 på 0x{cfg.pca9685_address:02X} "
        f"med {cfg.pca9685_frequency} Hz..."
    )
    driver.reset()
    time.sleep(0.01)

    servos = ServoArray(cfg.servo_configs, driver)

    # Start med alle i hjem så vi har en kjent referanse uansett hva
    # de stod på fra forrige kjøring.
    print("\nSetter alle servoer i hjemmeposisjon (utgangspunkt)...")
    servos.go_home()
    time.sleep(args.hold)

    try:
        for i, sc in enumerate(cfg.servo_configs):
            home = sc.home_angle_deg
            lo, hi = _safe_wiggle_targets(
                home, args.wiggle, sc.min_angle_deg, sc.max_angle_deg
            )
            print(
                f"\nServo {i} (kanal {sc.channel}): "
                f"home={home:.1f}°  wiggle {lo:.1f}° → {hi:.1f}°"
            )

            servos[i].set_angle(lo)
            print(f"  -> {lo:.1f}°")
            time.sleep(args.hold)

            servos[i].set_angle(hi)
            print(f"  -> {hi:.1f}°")
            time.sleep(args.hold)

            servos[i].set_angle(home)
            print(f"  -> hjem ({home:.1f}°)")
            time.sleep(args.hold)

        # Endelig hjemmeposisjon for alle samtidig — sikrer at alle
        # står på home_angle_deg når scriptet avsluttes.
        print("\nAlle servoer i hjem.")
        servos.go_home()
        time.sleep(args.settle)

    except KeyboardInterrupt:
        print("\nAvbrutt av bruker — prøver å sette alle i hjem.",
              file=sys.stderr)
        try:
            servos.go_home()
            time.sleep(args.settle)
        except Exception as exc:  # noqa: BLE001 — defensiv ved avbrudd
            print(f"  kunne ikke hjemstille: {exc}", file=sys.stderr)
    finally:
        if args.no_detach:
            print("Beholder PWM aktiv (--no-detach).")
        else:
            print("Frikobler alle kanaler (PWM av).")
            servos.detach_all()
        bus.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
