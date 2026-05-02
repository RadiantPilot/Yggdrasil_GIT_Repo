# check_home_geometry.py
# ======================
# Diagnose-skript: regner ut hvilke servovinkler IK-en gir ved
# Pose.home() for current config, og hvor mye home_height må
# justeres for å få vinklene nær 90°.
#
# Bruk dette under bringup når servoer "krasjer" i GUI-en med
# ValueError fra IK — det betyr som regel at geometrien i YAML-en
# ikke matcher den fysiske plattformen.
#
# Kjøres på dev-PC eller Pi (ingen hardware-avhengighet):
#     python scripts/check_home_geometry.py
#     python scripts/check_home_geometry.py --config config/min_config.yaml

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from stewart_platform.config.platform_config import PlatformConfig
from stewart_platform.geometry.platform_geometry import PlatformGeometry
from stewart_platform.geometry.pose import Pose
from stewart_platform.kinematics.inverse_kinematics import InverseKinematics


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sjekk hvilke vinkler IK gir ved Pose.home() med current config.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/default_config.yaml"),
        help="Sti til YAML-konfigurasjonsfil.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.config.exists():
        cfg = PlatformConfig.load(str(args.config))
        print(f"Lastet config fra {args.config}")
    else:
        cfg = PlatformConfig()
        print("Bruker default PlatformConfig (ingen YAML)")

    print(f"\nGeometri:")
    print(f"  base_radius     = {cfg.base_radius} mm")
    print(f"  platform_radius = {cfg.platform_radius} mm")
    print(f"  servo_horn_length = {cfg.servo_horn_length} mm")
    print(f"  rod_length        = {cfg.rod_length} mm")
    print(f"  home_height       = {cfg.home_height} mm (eksplisitt i YAML)")

    geometry = PlatformGeometry(cfg)
    ik = InverseKinematics(geometry, cfg.servo_configs)

    print(f"\nGeometri.compute_home_height() = {geometry.compute_home_height():.2f} mm")
    print(f"Faktisk home_height brukt        = {geometry.get_home_height():.2f} mm")

    print(f"\n--- IK ved Pose.home() ---")
    try:
        angles = ik.solve(Pose.home())
    except ValueError as exc:
        print(f"FEIL: IK kunne ikke løse Pose.home(): {exc}")
        return 1

    print(f"{'#':>3} {'beregnet':>10} {'home_cfg':>10} {'min':>6} {'max':>6} "
          f"{'margin OK':>10}")
    margin = cfg.safety_config.servo_angle_margin_deg
    all_ok = True
    for i, ang in enumerate(angles):
        sc = cfg.servo_configs[i]
        ok = sc.min_angle_deg + margin <= ang <= sc.max_angle_deg - margin
        all_ok = all_ok and ok
        flag = "OK" if ok else "** UTENFOR **"
        print(f"{i:>3} {ang:>10.2f} {sc.home_angle_deg:>10.2f} "
              f"{sc.min_angle_deg:>6.0f} {sc.max_angle_deg:>6.0f} {flag:>10}")

    if not all_ok:
        print(f"\nMinst én servo er utenfor sikkerhetsmargin "
              f"({margin}° fra grense).")
        print(f"Det betyr at IK ved Pose.home() ikke gir vinkler nær "
              f"home_angle_deg ({cfg.servo_configs[0].home_angle_deg}°).")
        print(f"Sannsynlige årsaker:")
        print(f"  - home_height ikke avstemt mot rod_length og horn_length")
        print(f"  - mounting_angle_deg gir ikke symmetrisk geometri")
        print(f"  - base/platform_joint_angles ikke korrekt for fysisk plattform")
    else:
        print(f"\nAlle servovinkler er innenfor margin ved Pose.home().")
    return 0


if __name__ == "__main__":
    sys.exit(main())
