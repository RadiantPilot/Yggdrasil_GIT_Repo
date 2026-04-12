# lsm6dsox_driver.py
# ==================
# Driver for LSM6DSOXTR IMU-sensor (akselerometer + gyroskop) over I2C.
# Montert på bunnplaten for å måle bunnplatens orientering.
# Akselerometer-/gyroskopområde og datahastighet er konfigurerbare.

from __future__ import annotations

from enum import Enum

from ..geometry.vector3 import Vector3
from .i2c_bus import I2CBus
from .imu_interface import IMUInterface


class AccelRange(Enum):
    """Målingsområde for akselerometeret.

    Høyere område gir større målekapasitet, men lavere oppløsning.
    For en Stewart-plattform er G2 eller G4 vanligvis tilstrekkelig.
    """
    G2 = 2     # ±2g  - høyest oppløsning
    G4 = 4     # ±4g
    G8 = 8     # ±8g
    G16 = 16   # ±16g - størst måleområde


class GyroRange(Enum):
    """Målingsområde for gyroskopet.

    Høyere område tillater raskere rotasjonsmåling, men med
    lavere oppløsning. DPS250 eller DPS500 passer for de fleste
    plattformapplikasjoner.
    """
    DPS125 = 125     # ±125 grader/s  - høyest oppløsning
    DPS250 = 250     # ±250 grader/s
    DPS500 = 500     # ±500 grader/s
    DPS1000 = 1000   # ±1000 grader/s
    DPS2000 = 2000   # ±2000 grader/s - størst måleområde


class DataRate(Enum):
    """Datahastighet (Output Data Rate) for sensoren.

    Bestemmer hvor ofte nye målinger er tilgjengelige.
    Bør settes lik eller høyere enn kontrollsløyfens frekvens.
    """
    ODR_12_5_HZ = 12.5
    ODR_26_HZ = 26.0
    ODR_52_HZ = 52.0
    ODR_104_HZ = 104.0
    ODR_208_HZ = 208.0
    ODR_416_HZ = 416.0
    ODR_833_HZ = 833.0


class LSM6DSOXDriver(IMUInterface):
    """Driver for LSM6DSOXTR 6-akset IMU (akselerometer + gyroskop).

    Kommuniserer over I2C med konfigurerbar adresse. Standard
    enhets-ID (WHO_AM_I) er 0x6C. Sensoren kan konfigureres med
    forskjellige måleområder og datahastigheter for optimal
    ytelse i den aktuelle applikasjonen.
    """

    def __init__(self, bus: I2CBus, address: int) -> None:
        """Opprett en ny LSM6DSOX-driver.

        Args:
            bus: I2C-bussinstans for kommunikasjon.
            address: I2C-adresse for sensoren (standard: 0x6A).
        """
        self._bus = bus
        self._address = address
        self._accel_range = AccelRange.G2
        self._gyro_range = GyroRange.DPS250
        self._data_rate = DataRate.ODR_104_HZ

    def configure(
        self,
        accel_range: AccelRange = AccelRange.G2,
        gyro_range: GyroRange = GyroRange.DPS250,
        data_rate: DataRate = DataRate.ODR_104_HZ,
    ) -> None:
        """Konfigurer sensorens måleområder og datahastighet.

        Skriver til CTRL1_XL og CTRL2_G registerene for å sette
        akselerometer- og gyroskopinnstillingene.

        Args:
            accel_range: Ønsket akselerometerområde (G2, G4, G8, G16).
            gyro_range: Ønsket gyroskopområde (DPS125-DPS2000).
            data_rate: Ønsket datahastighet (12.5-833 Hz).
        """
        raise NotImplementedError

    def read_acceleration(self) -> Vector3:
        """Les akselerasjonsdata fra sensorens OUTX/Y/Z_L/H_XL registre.

        Leser 6 bytes (2 per akse) og konverterer til m/s²
        basert på gjeldende måleområde.

        Returns:
            Vector3 med akselerasjon i m/s² for X, Y og Z-aksen.
        """
        raise NotImplementedError

    def read_gyroscope(self) -> Vector3:
        """Les gyroskopdata fra sensorens OUTX/Y/Z_L/H_G registre.

        Leser 6 bytes (2 per akse) og konverterer til grader/s
        basert på gjeldende måleområde.

        Returns:
            Vector3 med vinkelhastighet i grader/s for X, Y og Z-aksen.
        """
        raise NotImplementedError

    def read_temperature(self) -> float:
        """Les temperaturen fra OUT_TEMP_L/H registerene.

        Returns:
            Temperatur i grader Celsius.
        """
        raise NotImplementedError

    def who_am_i(self) -> int:
        """Les WHO_AM_I registeret (0x0F).

        Forventet verdi for LSM6DSOX er 0x6C.

        Returns:
            Enhets-ID (skal være 0x6C for LSM6DSOX).
        """
        raise NotImplementedError

    def reset(self) -> None:
        """Tilbakestill sensoren via SW_RESET bit i CTRL3_C registeret.

        Setter alle registre tilbake til standardverdier.
        Vent minst 10 ms etter tilbakestilling før ny konfigurasjon.
        """
        raise NotImplementedError
