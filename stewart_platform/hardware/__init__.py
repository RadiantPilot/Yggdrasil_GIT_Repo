# hardware
# ========
# Maskinvareabstraksjonspakke.
# Tilbyr enhetlige grensesnitt mot I2C-bussen, PCA9685 PWM-driver
# og IMU-sensor (LSM6DSOXTR på bunnplaten).
# Alle I2C-adresser er konfigurerbare via PlatformConfig.

from .i2c_bus import I2CBus
from .imu_interface import IMUInterface
from .lsm6dsox_driver import LSM6DSOXDriver, AccelRange, GyroRange, DataRate
from .pca9685_driver import PCA9685Driver

__all__ = [
    "I2CBus",
    "PCA9685Driver",
    "IMUInterface",
    "LSM6DSOXDriver",
    "AccelRange",
    "GyroRange",
    "DataRate",
]
