# bringup_imu.py
# ==============
# Standalone hardware-bringup-test for LSM6DSOXTR IMU.
# Verifiserer at sensoren svarer på riktig adresse, kan konfigureres,
# og leverer fornuftige målinger. Kjøres direkte på Raspberry Pi:
#
#     python scripts/bringup_imu.py
#
# Skriver ingenting til PCA9685 og beveger ingen servoer — helt trygt
# å kjøre uten strøm til servoene.

from __future__ import annotations

import sys
import time

from stewart_platform.hardware.i2c_bus import I2CBus
from stewart_platform.hardware.lsm6dsox_driver import LSM6DSOXDriver

I2C_BUS_NUMBER = 1
IMU_ADDRESS = 0x6A
EXPECTED_WHO_AM_I = 0x6C
NUM_SAMPLES = 5
SAMPLE_INTERVAL_S = 0.2


def main() -> int:
    bus = I2CBus(I2C_BUS_NUMBER)
    imu = LSM6DSOXDriver(bus, address=IMU_ADDRESS)

    who = imu.who_am_i()
    print(f"WHO_AM_I: 0x{who:02X}  (forventet 0x{EXPECTED_WHO_AM_I:02X})")
    if who != EXPECTED_WHO_AM_I:
        print("  !! Uventet ID — sjekk I2C-adresse og ledninger")
        bus.close()
        return 1

    imu.reset()
    imu.configure()
    time.sleep(0.05)

    print("\nLeser målinger (legg sensoren flatt og i ro):")
    print(f"  {'#':>2}  {'ax':>7} {'ay':>7} {'az':>7}  |  "
          f"{'gx':>7} {'gy':>7} {'gz':>7}  |  T")
    for i in range(NUM_SAMPLES):
        a = imu.read_acceleration()
        g = imu.read_angular_velocity()
        t = imu.read_temperature()
        print(f"  {i:>2}  {a.x:+7.2f} {a.y:+7.2f} {a.z:+7.2f}  |  "
              f"{g.x:+7.2f} {g.y:+7.2f} {g.z:+7.2f}  |  {t:.1f}°C")
        time.sleep(SAMPLE_INTERVAL_S)

    bus.close()
    print("\nFerdig — IMU svarer og leverer data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
