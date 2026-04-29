# lsm6dsox_driver.py
# ==================
# Driver for LSM6DSOXTR IMU-sensor (akselerometer + gyroskop) over I2C.
# Montert på bunnplaten for å måle bunnplatens orientering.
# Akselerometer-/gyroskopområde og datahastighet er konfigurerbare.

from __future__ import annotations

import time
from enum import Enum

from ..geometry.vector3 import Vector3
from .i2c_bus import I2CBus
from .imu_interface import IMUInterface


# Register-adresser (fra LSM6DSOX-databladet)
_WHO_AM_I = 0x0F
_CTRL1_XL = 0x10           # Akselerometer: ODR + måleområde
_CTRL2_G = 0x11            # Gyroskop: ODR + måleområde
_CTRL3_C = 0x12            # SW_RESET, BDU, IF_INC
_OUT_TEMP_L = 0x20         # Temperatur (2 bytes, little-endian)
_OUTX_L_G = 0x22           # Gyro X/Y/Z (6 bytes, little-endian)
_OUTX_L_A = 0x28           # Akselerometer X/Y/Z (6 bytes, little-endian)

# Forventet verdi i WHO_AM_I-registeret
_WHO_AM_I_EXPECTED = 0x6C

# CTRL3_C-bits
_CTRL3_SW_RESET = 0x01
_CTRL3_IF_INC = 0x04        # Auto-increment ved blokk-lesninger
_CTRL3_BDU = 0x40           # Block Data Update — sikrer konsistente 16-bit målinger

# Konverteringskonstanter
_GRAVITY_MS2 = 9.80665
_TEMP_SENSITIVITY = 256.0   # LSB per °C
_TEMP_REFERENCE_C = 25.0    # T0 i datablad


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


# Bit-mønster i CTRL1_XL[3:2] for akselerometerområde.
# Merk at koding ikke er numerisk sortert (jf. databladet, Tabell 51).
_ACCEL_RANGE_BITS = {
    AccelRange.G2: 0x00,
    AccelRange.G16: 0x04,
    AccelRange.G4: 0x08,
    AccelRange.G8: 0x0C,
}

# Sensitivitet i mg per LSB (jf. databladet, Tabell 3).
_ACCEL_SENSITIVITY_MG_PER_LSB = {
    AccelRange.G2: 0.061,
    AccelRange.G4: 0.122,
    AccelRange.G8: 0.244,
    AccelRange.G16: 0.488,
}

# Bit-mønster i CTRL2_G[3:1] for gyroskopområde.
# DPS125 settes via FS_125-bit (bit 1), de andre via FS_G[1:0] (bit 3:2).
_GYRO_RANGE_BITS = {
    GyroRange.DPS125: 0x02,
    GyroRange.DPS250: 0x00,
    GyroRange.DPS500: 0x04,
    GyroRange.DPS1000: 0x08,
    GyroRange.DPS2000: 0x0C,
}

# Sensitivitet i mdps (millidegrees/s) per LSB.
_GYRO_SENSITIVITY_MDPS_PER_LSB = {
    GyroRange.DPS125: 4.375,
    GyroRange.DPS250: 8.75,
    GyroRange.DPS500: 17.5,
    GyroRange.DPS1000: 35.0,
    GyroRange.DPS2000: 70.0,
}

# Bit-mønster i CTRL[7:4] for ODR. Samme koding for både akselerometer og gyroskop.
_DATA_RATE_BITS = {
    DataRate.ODR_12_5_HZ: 0x10,
    DataRate.ODR_26_HZ: 0x20,
    DataRate.ODR_52_HZ: 0x30,
    DataRate.ODR_104_HZ: 0x40,
    DataRate.ODR_208_HZ: 0x50,
    DataRate.ODR_416_HZ: 0x60,
    DataRate.ODR_833_HZ: 0x70,
}


def _twos_complement_16(low: int, high: int) -> int:
    """Slå sammen lav og høy byte til signert 16-bit heltall."""
    val = (high << 8) | low
    if val & 0x8000:
        val -= 0x10000
    return val


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
        self._gyro_bias_dps = Vector3(0.0, 0.0, 0.0)
        self._accel_offset_ms2 = Vector3(0.0, 0.0, 0.0)

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
        self._accel_range = accel_range
        self._gyro_range = gyro_range
        self._data_rate = data_rate

        odr_bits = _DATA_RATE_BITS[data_rate]
        ctrl1_xl = odr_bits | _ACCEL_RANGE_BITS[accel_range]
        ctrl2_g = odr_bits | _GYRO_RANGE_BITS[gyro_range]

        self._bus.write_byte_data(self._address, _CTRL1_XL, ctrl1_xl)
        self._bus.write_byte_data(self._address, _CTRL2_G, ctrl2_g)
        # BDU sikrer at høy og lav byte i en 16-bit måling kommer fra samme sample.
        # IF_INC tillater blokk-lesninger av 6 byte data i én transaksjon.
        self._bus.write_byte_data(
            self._address, _CTRL3_C, _CTRL3_BDU | _CTRL3_IF_INC
        )

    def read_acceleration(self) -> Vector3:
        """Les akselerasjonsdata fra sensorens OUTX/Y/Z_L/H_XL registre.

        Leser 6 bytes (2 per akse) og konverterer til m/s²
        basert på gjeldende måleområde.

        Returns:
            Vector3 med akselerasjon i m/s² for X, Y og Z-aksen.
        """
        raw = self._read_accel_raw_ms2()
        return Vector3(
            raw.x - self._accel_offset_ms2.x,
            raw.y - self._accel_offset_ms2.y,
            raw.z - self._accel_offset_ms2.z,
        )

    def read_angular_velocity(self) -> Vector3:
        """Les gyroskopdata fra sensorens OUTX/Y/Z_L/H_G registre.

        Leser 6 bytes (2 per akse) og konverterer til grader/s
        basert på gjeldende måleområde.

        Returns:
            Vector3 med vinkelhastighet i grader/s for X, Y og Z-aksen.
        """
        raw = self._read_gyro_raw_dps()
        return Vector3(
            raw.x - self._gyro_bias_dps.x,
            raw.y - self._gyro_bias_dps.y,
            raw.z - self._gyro_bias_dps.z,
        )

    def read_temperature(self) -> float:
        """Les temperaturen fra OUT_TEMP_L/H registerene.

        Returns:
            Temperatur i grader Celsius.
        """
        data = self._bus.read_block_data(self._address, _OUT_TEMP_L, 2)
        raw = _twos_complement_16(data[0], data[1])
        return raw / _TEMP_SENSITIVITY + _TEMP_REFERENCE_C

    def who_am_i(self) -> int:
        """Les WHO_AM_I registeret (0x0F).

        Forventet verdi for LSM6DSOX er 0x6C.

        Returns:
            Enhets-ID (skal være 0x6C for LSM6DSOX).
        """
        return self._bus.read_byte_data(self._address, _WHO_AM_I)

    def reset(self) -> None:
        """Tilbakestill sensoren via SW_RESET bit i CTRL3_C registeret.

        Setter alle registre tilbake til standardverdier.
        Vent minst 10 ms etter tilbakestilling før ny konfigurasjon.
        """
        self._bus.write_byte_data(self._address, _CTRL3_C, _CTRL3_SW_RESET)
        # Datablad spesifiserer < 50 us, men vi bruker god margin.
        time.sleep(0.05)

    def calibrate_gyro_bias(self, num_samples: int = 200) -> None:
        """Kalibrer gyroskopets nullpunktsfeil (bias).

        Leser samples mens sensoren er i ro og beregner
        gjennomsnittlig offset. Sensoren MÅ være helt stille
        under kalibrering, ellers fanges bevegelse opp som bias.

        Args:
            num_samples: Antall målinger som skal gjennomsnittes.
        """
        sum_x = sum_y = sum_z = 0.0
        for _ in range(num_samples):
            raw = self._read_gyro_raw_dps()
            sum_x += raw.x
            sum_y += raw.y
            sum_z += raw.z
            time.sleep(0.005)
        self._gyro_bias_dps = Vector3(
            sum_x / num_samples,
            sum_y / num_samples,
            sum_z / num_samples,
        )

    def calibrate_accelerometer_offset(self, num_samples: int = 200) -> None:
        """Kalibrer akselerometerets offset.

        Leser samples mens sensoren er vannrett og i ro. Antar
        at Z-aksen peker oppover, slik at forventet avlesning er
        (0, 0, +g). Avviket fra dette lagres som offset.

        Args:
            num_samples: Antall målinger som skal gjennomsnittes.
        """
        sum_x = sum_y = sum_z = 0.0
        for _ in range(num_samples):
            raw = self._read_accel_raw_ms2()
            sum_x += raw.x
            sum_y += raw.y
            sum_z += raw.z
            time.sleep(0.005)
        avg_x = sum_x / num_samples
        avg_y = sum_y / num_samples
        avg_z = sum_z / num_samples
        # Forventet verdi når sensoren ligger flatt: (0, 0, +g).
        self._accel_offset_ms2 = Vector3(avg_x, avg_y, avg_z - _GRAVITY_MS2)

    def _read_accel_raw_ms2(self) -> Vector3:
        """Råavlesning av akselerometeret i m/s² (uten offset-korreksjon)."""
        data = self._bus.read_block_data(self._address, _OUTX_L_A, 6)
        x = _twos_complement_16(data[0], data[1])
        y = _twos_complement_16(data[2], data[3])
        z = _twos_complement_16(data[4], data[5])
        # mg/LSB -> g/LSB -> m/s²/LSB
        scale = _ACCEL_SENSITIVITY_MG_PER_LSB[self._accel_range] * 1e-3 * _GRAVITY_MS2
        return Vector3(x * scale, y * scale, z * scale)

    def _read_gyro_raw_dps(self) -> Vector3:
        """Råavlesning av gyroskopet i grader/s (uten bias-korreksjon)."""
        data = self._bus.read_block_data(self._address, _OUTX_L_G, 6)
        x = _twos_complement_16(data[0], data[1])
        y = _twos_complement_16(data[2], data[3])
        z = _twos_complement_16(data[4], data[5])
        # mdps/LSB -> dps/LSB
        scale = _GYRO_SENSITIVITY_MDPS_PER_LSB[self._gyro_range] * 1e-3
        return Vector3(x * scale, y * scale, z * scale)
