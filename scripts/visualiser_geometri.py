# visualiser_geometri.py
# ======================
# Tegner plattformens 3D-geometri med matplotlib.
# Viser bunnledd, toppplatens ledd og beinene mellom dem
# for tre scenarier: hjemmeposisjon, roll=15° og pitch=15°.
#
# Ingen hardware-avhengighet — kjøres på dev-PC.
# Krever matplotlib:  pip install matplotlib
#
# Kjøring:
#     python scripts/visualiser_geometri.py
#     python scripts/visualiser_geometri.py --config config/min_config.yaml

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (registrerer 3D-projeksjonen)
    import numpy as np
except ImportError:
    print("matplotlib er ikke installert.")
    print("Installer med:  pip install matplotlib")
    sys.exit(1)

from stewart_platform.config.platform_config import PlatformConfig
from stewart_platform.geometry.platform_geometry import PlatformGeometry
from stewart_platform.geometry.pose import Pose
from stewart_platform.geometry.vector3 import Vector3


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualiser Stewart-plattformens 3D-geometri.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent.parent / "config" / "default_config.yaml",
        help="Sti til YAML-konfigurasjonsfil.",
    )
    return parser.parse_args()


def _sirkelomriss(radius: float, z: float, n: int = 64) -> tuple:
    vinkler = np.linspace(0, 2 * math.pi, n)
    return radius * np.cos(vinkler), radius * np.sin(vinkler), np.full(n, z)


def _tegn_scenario(ax: "plt.Axes", geometry: PlatformGeometry, pose: Pose, tittel: str) -> None:
    base_ledd = geometry.get_base_joints()
    topp_ledd = geometry.get_platform_joints_world(pose)
    h = geometry.get_home_height()

    # Bunnplatens ledd
    bx = [v.x for v in base_ledd]
    by = [v.y for v in base_ledd]
    bz = [v.z for v in base_ledd]
    ax.scatter(bx, by, bz, color="steelblue", s=60, zorder=5, label="Bunnledd")

    # Toppplatens ledd
    tx = [v.x for v in topp_ledd]
    ty = [v.y for v in topp_ledd]
    tz = [v.z for v in topp_ledd]
    ax.scatter(tx, ty, tz, color="firebrick", s=60, zorder=5, label="Toppplatens ledd")

    # Bein (grå linjer)
    for i in range(6):
        ax.plot(
            [bx[i], tx[i]],
            [by[i], ty[i]],
            [bz[i], tz[i]],
            color="gray",
            linewidth=1.5,
        )

    # Sirkelomriss for base og platform
    base_r = geometry._base_radius
    plat_r = geometry._platform_radius
    cx, cy, cz = _sirkelomriss(base_r, 0.0)
    ax.plot(cx, cy, cz, color="steelblue", linestyle="--", linewidth=0.8, alpha=0.5)
    cx, cy, cz = _sirkelomriss(plat_r, h)
    ax.plot(cx, cy, cz, color="firebrick", linestyle="--", linewidth=0.8, alpha=0.5)

    # Toppplate-polygon (lukket)
    tx_c = tx + [tx[0]]
    ty_c = ty + [ty[0]]
    tz_c = tz + [tz[0]]
    ax.plot(tx_c, ty_c, tz_c, color="firebrick", linewidth=1.0, alpha=0.6)

    # Akse-innstillinger
    r = base_r * 1.3
    ax.set_xlim(-r, r)
    ax.set_ylim(-r, r)
    ax.set_zlim(0, h * 1.4)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_zlabel("Z (mm)")
    ax.set_title(tittel, fontsize=10, pad=6)
    ax.view_init(elev=25, azim=45)

    if tittel.startswith("Hjemme"):
        ax.legend(fontsize=7, loc="upper left")


def main() -> int:
    args = _parse_args()

    if args.config.exists():
        cfg = PlatformConfig.load(str(args.config))
        print(f"Lastet config fra {args.config}")
    else:
        cfg = PlatformConfig()
        print("Bruker default PlatformConfig (ingen YAML funnet)")

    geometry = PlatformGeometry(cfg)

    scenarier = [
        (Pose.home(),                                        "Hjemmeposisjon  (roll=0°, pitch=0°)"),
        (Pose(rotation=Vector3(x=15.0, y=0.0, z=0.0)),     "Roll = +15°"),
        (Pose(rotation=Vector3(x=0.0, y=15.0, z=0.0)),     "Pitch = +15°"),
    ]

    fig = plt.figure(figsize=(15, 5))
    fig.suptitle("Stewart Platform — 3D-geometri", fontsize=13, fontweight="bold")

    for idx, (pose, tittel) in enumerate(scenarier, start=1):
        ax = fig.add_subplot(1, 3, idx, projection="3d")
        _tegn_scenario(ax, geometry, pose, tittel)

    plt.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
