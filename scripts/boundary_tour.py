# boundary_tour.py
# =================
# Beveger plattformen gjennom 8 posisjoner nær grenseområdet (25° rotasjon),
# før den returnerer til senter og slår av.
#
# Kjøres på Pi:
#     python scripts/boundary_tour.py
#     python scripts/boundary_tour.py --amplitude 20 --dwell 2.0
#     python scripts/boundary_tour.py --config config/min_config.yaml

from __future__ import annotations

import argparse
import math
import sys
import time

from stewart_platform.config.platform_config import PlatformConfig
from stewart_platform.control.motion_controller import MotionController
from stewart_platform.geometry.pose import Pose
from stewart_platform.geometry.vector3 import Vector3

# Grensepunkter som vektorer i (roll, pitch, yaw).
# 8 retninger rundt enhetsirkelen pluss rent yaw — dekker workspace-kanten.
_RETNINGER = [
    ("Nord  (pitch+)",     ( 0.0,  1.0,  0.0)),
    ("NØ    (roll+ pitch+)", ( 1.0,  1.0,  0.0)),
    ("Øst   (roll+)",       ( 1.0,  0.0,  0.0)),
    ("SØ    (roll+ pitch-)", ( 1.0, -1.0,  0.0)),
    ("Sør   (pitch-)",      ( 0.0, -1.0,  0.0)),
    ("SV    (roll- pitch-)", (-1.0, -1.0,  0.0)),
    ("Vest  (roll-)",       (-1.0,  0.0,  0.0)),
    ("NV    (roll- pitch+)", (-1.0,  1.0,  0.0)),
]


def _normaliser(v: tuple[float, float, float]) -> tuple[float, float, float]:
    mag = math.sqrt(sum(x * x for x in v))
    return tuple(x / mag for x in v)  # type: ignore[return-value]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Boundary-tur: beveger plattformen nær grenseområdet og tilbake til senter.",
    )
    parser.add_argument(
        "--amplitude",
        type=float,
        default=25.0,
        help="Rotasjonsvinkel i grader for hvert grensepunkt (default 25.0).",
    )
    parser.add_argument(
        "--dwell",
        type=float,
        default=1.5,
        help="Dveletid i sekunder ved hvert grensepunkt (default 1.5).",
    )
    parser.add_argument(
        "--transition",
        type=float,
        default=1.0,
        help="Tid i sekunder for overgang mellom posisjoner (default 1.0).",
    )
    parser.add_argument(
        "--config",
        default="config/default_config.yaml",
        help="Sti til YAML-konfigurasjonsfil.",
    )
    return parser.parse_args()


def _sett_pose_gradvis(
    ctrl: MotionController,
    fra: Pose,
    til: Pose,
    varighet: float,
    trinn_hz: float = 25.0,
) -> None:
    """Interpoler jevnt fra én pose til en annen over oppgitt varighet."""
    dt = 1.0 / trinn_hz
    steg = max(1, int(round(varighet * trinn_hz)))
    for i in range(1, steg + 1):
        t = i / steg
        pose = fra.interpolate(til, t)
        ctrl.set_target_pose(pose)
        time.sleep(dt)


def main() -> int:
    args = _parse_args()
    amplitude: float = args.amplitude
    dwell: float = args.dwell
    transition: float = args.transition

    print(f"Laster konfigurasjon fra '{args.config}'...")
    try:
        config = PlatformConfig.load(args.config)
    except FileNotFoundError as e:
        print(f"FEIL: {e}")
        return 2

    maks_rot = config.safety_config.max_rotation_deg
    if amplitude >= maks_rot:
        print(
            f"ADVARSEL: --amplitude {amplitude}° >= max_rotation_deg {maks_rot}°. "
            f"Begrenser til {maks_rot * 0.85:.1f}°."
        )
        amplitude = maks_rot * 0.85

    print(f"Initialiserer kontroller (amplitude={amplitude}°, dvele={dwell}s)...")
    ctrl = MotionController(config)

    def _sikkerhetsvarsling(severity, violations):  # type: ignore[no-untyped-def]
        for v in violations:
            print(f"  [{severity.name}] {v}")

    ctrl.add_safety_listener(_sikkerhetsvarsling)

    try:
        ctrl.initialize()
        ctrl.start()
        time.sleep(0.5)  # La PID-regulatoren stabilisere seg

        print("\nStarter boundary-tur...\n")
        forrige_pose = Pose.home()

        for navn, retning in _RETNINGER:
            nr, np_, nw = _normaliser(retning)
            maalpunkt = Pose(
                rotation=Vector3(
                    nr * amplitude,
                    np_ * amplitude,
                    nw * amplitude,
                )
            )
            print(f"  -> {navn:25s}  (roll={nr*amplitude:+.1f}°, pitch={np_*amplitude:+.1f}°)")

            # Beveg til grensepunktet
            _sett_pose_gradvis(ctrl, forrige_pose, maalpunkt, transition)

            # Dvel
            time.sleep(dwell)
            forrige_pose = maalpunkt

        # Returner til senter
        print(f"\n  -> Senter (0°, 0°, 0°)")
        _sett_pose_gradvis(ctrl, forrige_pose, Pose.home(), transition)
        time.sleep(dwell)

        print("\nBoundary-tur ferdig. Plattformen er i senter.")

    except KeyboardInterrupt:
        print("\nAvbrutt av bruker.")
    finally:
        print("Stopper og frikobler servoer...")
        ctrl.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
