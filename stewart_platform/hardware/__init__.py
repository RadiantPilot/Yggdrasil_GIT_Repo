# hardware
# ========
# Maskinvareabstraksjonspakke.
# Tilbyr enhetlige grensesnitt mot I2C-bussen, PCA9685 PWM-driver,
# IMU-sensorer og det fysiske knappekortet.
# Alle I2C-adresser er konfigurerbare via PlatformConfig.

from .attiny_i2c_buttons import AttinyI2CButtons
from .button_interface import ButtonInterface
from .i2c_bus import I2CBus
from .imu_interface import IMUInterface
from .lsm6dsox_driver import LSM6DSOXDriver, AccelRange, GyroRange, DataRate
from .lsm9ds1_driver import (
    LSM9DS1Driver,
    LSM9DS1AccelRange,
    LSM9DS1GyroRange,
    LSM9DS1DataRate,
)
from .mock_buttons import MockButtons
from .pca9685_driver import PCA9685Driver
from .rpi_gpio_buttons import RPiGPIOButtons

__all__ = [
    "I2CBus",
    "PCA9685Driver",
    "IMUInterface",
    "LSM6DSOXDriver",
    "AccelRange",
    "GyroRange",
    "DataRate",
    "LSM9DS1Driver",
    "LSM9DS1AccelRange",
    "LSM9DS1GyroRange",
    "LSM9DS1DataRate",
    "ButtonInterface",
    "MockButtons",
    "RPiGPIOButtons",
    "AttinyI2CButtons",
]
