# lsm9ds1_driver.py
# ==================
# Driver for LSM9DS1 9-akset IMU (akselerometer + gyroskop + magnetometer) over I2C.
# Akselerometer og gyroskop deler én I2C-adresse; magnetometeret har sin egen.
# Magnetometeret initialiseres til hvilemodus og kan leses via read_magnetic_field().

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Optional

_logger = logging.getLogger(__name__)

from ..geometry.vector3 import Vector3
from .i2c_bus import I2CBus
from .imu_interface import IMUInterface


# ---------------------------------------------------------------------------
# Akselerometer/Gyroskop-registre (fra LSM9DS1-databladet, seksjon 7.1)
# ---------------------------------------------------------------------------
_WHO_AM_I         = 0x0F   # Identifikasjonsregister
_CTRL_REG1_G      = 0x10   # Gyroskop: ODR + fullskala
_CTRL_REG4        = 0x1E   # Aktiver gyroskop-akser (X/Y/Z)
_CTRL_REG5_XL     = 0x1F   # Aktiver akselerometer-akser (X/Y/Z)
_CTRL_REG6_XL     = 0x20   # Akselerometer: ODR + fullskala
_CTRL_REG8        = 0x22   # SW_RESET, BDU, IF_ADD_INC
_OUT_TEMP_L       = 0x15   # Temperatur (2 bytes, little-endian)
_OUT_X_L_G        = 0x18   # Gyroskop X/Y/Z (6 bytes, little-endian)
_OUT_X_L_XL       = 0x28   # Akselerometer X/Y/Z (6 bytes, little-endian)

# Forventet verdi i WHO_AM_I for akselerometer/gyroskop-delen
_WHO_AM_I_XG_EXPECTED = 0x68

# CTRL_REG8-bits
_CTRL8_SW_RESET  = 0x01    # Software reset
_CTRL8_IF_ADD_INC = 0x04   # Auto-increment adresse ved blokk-lesninger
_CTRL8_BDU       = 0x40    # Block Data Update — konsistente 16-bit målinger

# CTRL_REG4: Aktiver alle tre gyroskop-akser (bit 3, 2, 1)
_CTRL4_ALL_GYRO  = 0x38

# CTRL_REG5_XL: Aktiver alle tre akselerometer-akser (bit 5, 4, 3)
_CTRL5_ALL_XL    = 0x38

# Temperaturkonvertering
_TEMP_SENSITIVITY = 16.0   # LSB per °C (LSM9DS1 databladet, Tabell 3)
_TEMP_REFERENCE_C = 25.0   # Referansetemperatur ved 0 LSB

# Tyngdeakselerasjon
_GRAVITY_MS2 = 9.80665

# ---------------------------------------------------------------------------
# Magnetometer-registre (LSM9DS1-databladet, seksjon 7.2)
# ---------------------------------------------------------------------------
_MAG_WHO_AM_I    = 0x0F    # Identifikasjonsregister for magnetometer
_MAG_CTRL_REG1_M = 0x20    # Ytelsesmodus XY, ODR
_MAG_CTRL_REG2_M = 0x21    # Fullskala
_MAG_CTRL_REG3_M = 0x22    # Driftsmodus (continuous / single / power-down)
_MAG_CTRL_REG4_M = 0x23    # Ytelsesmodus Z + liten-endian
_MAG_OUT_X_L_M   = 0x28    # Magnetometer X/Y/Z (6 bytes, little-endian)

# Forventet verdi i WHO_AM_I for magnetometer-delen
_WHO_AM_I_M_EXPECTED = 0x3D

# Magnetometer-driftsmoduser (CTRL_REG3_M bits [1:0])
_MAG_MODE_CONTINUOUS = 0x00
_MAG_MODE_POWER_DOWN = 0x03

# Magnetometer ytelsesmodus for XY-akser (CTRL_REG1_M bits [6:5])
_MAG_PERF_HIGH = 0x60      # Høy ytelse

# Magnetometer ytelsesmodus for Z-akse (CTRL_REG4_M bits [3:2])
_MAG_PERF_Z_HIGH = 0x04    # Høy ytelse

# BDU for magnetometer (CTRL_REG5_M bit 6)
_MAG_BDU = 0x40


class LSM9DS1AccelRange(Enum):
    """Målingsområde for akselerometeret (LSM9DS1).

    Høyere område gir større målekapasitet, men lavere oppløsning.
    G2 er tilstrekkelig for en Stewart-plattform i rolig drift.
    """
    G2  = 2    # ±2g  — høyest oppløsning
    G4  = 4    # ±4g
    G8  = 8    # ±8g
    G16 = 16   # ±16g — størst måleområde


class LSM9DS1GyroRange(Enum):
    """Målingsområde for gyroskopet (LSM9DS1).

    DPS245 dekker de fleste plattformapplikasjoner.
    """
    DPS245  = 245   # ±245 grader/s  — høyest oppløsning
    DPS500  = 500   # ±500 grader/s
    DPS2000 = 2000  # ±2000 grader/s — størst måleområde


class LSM9DS1DataRate(Enum):
    """Datahastighet (Output Data Rate) for LSM9DS1.

    Gjelder både akselerometer og gyroskop. Velg lik eller høyere enn
    kontrollsløyfens frekvens for optimalt sensorutnyttelse.
    """
    ODR_14_9_HZ = 14.9
    ODR_59_5_HZ = 59.5
    ODR_119_HZ  = 119.0
    ODR_238_HZ  = 238.0
    ODR_476_HZ  = 476.0
    ODR_952_HZ  = 952.0


# Bit-mønster i CTRL_REG1_G bits [7:5] for gyroskop-ODR
_GYRO_ODR_BITS = {
    LSM9DS1DataRate.ODR_14_9_HZ: 0x20,
    LSM9DS1DataRate.ODR_59_5_HZ: 0x40,
    LSM9DS1DataRate.ODR_119_HZ:  0x60,
    LSM9DS1DataRate.ODR_238_HZ:  0x80,
    LSM9DS1DataRate.ODR_476_HZ:  0xA0,
    LSM9DS1DataRate.ODR_952_HZ:  0xC0,
}

# Bit-mønster i CTRL_REG1_G bits [4:3] for gyroskop-fullskala
_GYRO_FS_BITS = {
    LSM9DS1GyroRange.DPS245:  0x00,
    LSM9DS1GyroRange.DPS500:  0x08,
    LSM9DS1GyroRange.DPS2000: 0x18,
}

# Sensitivitet i mdps per LSB (databladet Tabell 3)
_GYRO_SENSITIVITY_MDPS_PER_LSB = {
    LSM9DS1GyroRange.DPS245:  8.75,
    LSM9DS1GyroRange.DPS500:  17.5,
    LSM9DS1GyroRange.DPS2000: 70.0,
}

# Bit-mønster i CTRL_REG6_XL bits [7:5] for akselerometer-ODR
_ACCEL_ODR_BITS = {
    LSM9DS1DataRate.ODR_14_9_HZ: 0x20,
    LSM9DS1DataRate.ODR_59_5_HZ: 0x40,
    LSM9DS1DataRate.ODR_119_HZ:  0x60,
    LSM9DS1DataRate.ODR_238_HZ:  0x80,
    LSM9DS1DataRate.ODR_476_HZ:  0xA0,
    LSM9DS1DataRate.ODR_952_HZ:  0xC0,
}

# Bit-mønster i CTRL_REG6_XL bits [4:3] for akselerometer-fullskala
# NB: kodingen er ikke numerisk sortert (databladet Tabell 67)
_ACCEL_FS_BITS = {
    LSM9DS1AccelRange.G2:  0x00,
    LSM9DS1AccelRange.G16: 0x08,
    LSM9DS1AccelRange.G4:  0x10,
    LSM9DS1AccelRange.G8:  0x18,
}

# Sensitivitet i mg per LSB (databladet Tabell 3)
_ACCEL_SENSITIVITY_MG_PER_LSB = {
    LSM9DS1AccelRange.G2:  0.061,
    LSM9DS1AccelRange.G4:  0.122,
    LSM9DS1AccelRange.G8:  0.244,
    LSM9DS1AccelRange.G16: 0.732,
}

# Magnetometer fullskala-bits i CTRL_REG2_M bits [6:5]
_MAG_FS_BITS = {
    4:  0x00,   # ±4 gauss
    8:  0x20,   # ±8 gauss
    12: 0x40,   # ±12 gauss
    16: 0x60,   # ±16 gauss
}

# Magnetometer sensitivitet i µT per LSB (1 gauss = 100 µT)
_MAG_SENSITIVITY_UT_PER_LSB = {
    4:  0.014,   # 0.14 mgauss/LSB = 0.014 µT/LSB
    8:  0.029,
    12: 0.043,
    16: 0.058,
}

# Standard magnetometer fullskala i gauss
_MAG_DEFAULT_FS_GAUSS = 4


def _twos_complement_16(low: int, high: int) -> int:
    """Slå sammen lav og høy byte til signert 16-bit heltall."""
    val = (high << 8) | low
    if val & 0x8000:
        val -= 0x10000
    return val


class LSM9DS1Driver(IMUInterface):
    """Driver for LSM9DS1 9-akset IMU (akselerometer + gyroskop + magnetometer).

    Akselerometer og gyroskop kommuniserer over én I2C-adresse (accel_gyro_address).
    Magnetometeret har en separat I2C-adresse (mag_address) — dette er en hardvare-
    egenskap ved LSM9DS1-chipen.

    Magnetometeret initialiseres til hvilemodus i konstruktøren for å sette det i
    en kjent tilstand. Det kan leses via read_magnetic_field() når ønskelig.
    """

    def __init__(
        self,
        bus: I2CBus,
        accel_gyro_address: int,
        mag_address: int,
    ) -> None:
        """Opprett en ny LSM9DS1-driver.

        Args:
            bus: I2C-bussinstans for kommunikasjon.
            accel_gyro_address: I2C-adresse for akselerometer/gyroskop (0x6A eller 0x6B).
            mag_address: I2C-adresse for magnetometeret (0x1C eller 0x1E).
        """
        self._bus = bus
        self._ag_address = accel_gyro_address
        self._mag_address = mag_address

        self._accel_range = LSM9DS1AccelRange.G2
        self._gyro_range = LSM9DS1GyroRange.DPS245
        self._data_rate = LSM9DS1DataRate.ODR_119_HZ
        self._mag_fs_gauss = _MAG_DEFAULT_FS_GAUSS

        self._gyro_bias_dps = Vector3(0.0, 0.0, 0.0)
        self._accel_offset_ms2 = Vector3(0.0, 0.0, 0.0)

        # Cache for siste vellykkede I2C-lesing — returneres ved kommunikasjonsfeil
        self._last_accel_raw = Vector3(0.0, 0.0, _GRAVITY_MS2)
        self._last_gyro_raw = Vector3(0.0, 0.0, 0.0)
        self._last_mag_raw: Optional[Vector3] = None

        # Sett magnetometeret i hvilemodus (kjent tilstand) ved opprettelse.
        # Dette forhindrer at mag-delen av chipen oppfører seg uforutsigbart
        # og interfererer med akselerometer/gyroskop-lesninger.
        try:
            self._bus.write_byte_data(self._mag_address, _MAG_CTRL_REG3_M, _MAG_MODE_POWER_DOWN)
        except OSError as exc:
            _logger.warning("Kunne ikke sette magnetometer i hvilemodus: %s", exc)

    def configure(
        self,
        accel_range: LSM9DS1AccelRange = LSM9DS1AccelRange.G2,
        gyro_range: LSM9DS1GyroRange = LSM9DS1GyroRange.DPS245,
        data_rate: LSM9DS1DataRate = LSM9DS1DataRate.ODR_119_HZ,
    ) -> None:
        """Konfigurer sensorens måleområder og datahastighet.

        Skriver til CTRL_REG1_G (gyroskop) og CTRL_REG6_XL (akselerometer)
        for å sette ODR og fullskala. Aktiverer alle tre akser.

        Args:
            accel_range: Ønsket akselerometerområde.
            gyro_range: Ønsket gyroskopområde.
            data_rate: Ønsket datahastighet for begge sensorer.
        """
        self._accel_range = accel_range
        self._gyro_range = gyro_range
        self._data_rate = data_rate

        gyro_reg = _GYRO_ODR_BITS[data_rate] | _GYRO_FS_BITS[gyro_range]
        accel_reg = _ACCEL_ODR_BITS[data_rate] | _ACCEL_FS_BITS[accel_range]

        self._bus.write_byte_data(self._ag_address, _CTRL_REG1_G, gyro_reg)
        # BDU sikrer at høy og lav byte i en 16-bit måling kommer fra samme sample.
        # IF_ADD_INC tillater blokk-lesninger av 6 byte i én I2C-transaksjon.
        self._bus.write_byte_data(
            self._ag_address, _CTRL_REG8, _CTRL8_BDU | _CTRL8_IF_ADD_INC
        )
        self._bus.write_byte_data(self._ag_address, _CTRL_REG6_XL, accel_reg)
        self._bus.write_byte_data(self._ag_address, _CTRL_REG4, _CTRL4_ALL_GYRO)
        self._bus.write_byte_data(self._ag_address, _CTRL_REG5_XL, _CTRL5_ALL_XL)

    def read_acceleration(self) -> Vector3:
        """Les akselerasjonsdata fra OUT_X/Y/Z_L/H_XL-registrene.

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
        """Les gyroskopdata fra OUT_X/Y/Z_L/H_G-registrene.

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
        """Les temperaturen fra OUT_TEMP_L/H-registrene.

        Returns:
            Temperatur i grader Celsius.
        """
        data = self._bus.read_block_data(self._ag_address, _OUT_TEMP_L, 2)
        raw = _twos_complement_16(data[0], data[1])
        return raw / _TEMP_SENSITIVITY + _TEMP_REFERENCE_C

    def who_am_i(self) -> int:
        """Les WHO_AM_I-registeret for akselerometer/gyroskop-delen (0x0F).

        Forventet verdi for LSM9DS1 er 0x68.

        Returns:
            Enhets-ID (skal være 0x68 for LSM9DS1).
        """
        return self._bus.read_byte_data(self._ag_address, _WHO_AM_I)

    def who_am_i_mag(self) -> int:
        """Les WHO_AM_I-registeret for magnetometer-delen (0x0F).

        Forventet verdi for LSM9DS1 er 0x3D.

        Returns:
            Enhets-ID for magnetometeret (skal være 0x3D).
        """
        return self._bus.read_byte_data(self._mag_address, _MAG_WHO_AM_I)

    def reset(self) -> None:
        """Tilbakestill akselerometer/gyroskop-delen via SW_RESET i CTRL_REG8.

        Setter alle registre tilbake til standardverdier.
        Vent minst 10 ms etter tilbakestilling før ny konfigurasjon.
        """
        self._bus.write_byte_data(self._ag_address, _CTRL_REG8, _CTRL8_SW_RESET)
        # Datablad spesifiserer < 50 µs, men vi bruker god margin.
        time.sleep(0.05)

    def calibrate_gyro_bias(self, num_samples: int = 200) -> None:
        """Kalibrer gyroskopets nullpunktsfeil (bias).

        Leser samples mens sensoren er i ro og beregner gjennomsnittlig
        offset. Sensoren MÅ være helt stille under kalibrering.

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

        Leser samples mens sensoren er vannrett og i ro. Antar at Z-aksen
        peker oppover, slik at forventet avlesning er (0, 0, +g).

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

    def read_magnetic_field(self) -> Optional[Vector3]:
        """Les magnetfeltdata fra OUT_X/Y/Z_L/H_M-registrene.

        Magnetometeret må ha vært konfigurert med configure_magnetometer()
        før denne metoden gir meningsfulle data. Returnerer siste kjente
        verdi ved I2C-feil.

        Returns:
            Vector3 med magnetfelt i µT for X, Y og Z-aksen.
        """
        try:
            data = self._bus.read_block_data(self._mag_address, _MAG_OUT_X_L_M, 6)
        except OSError as exc:
            _logger.warning("I2C-lesing av magnetometer feilet: %s — returnerer siste verdi", exc)
            return self._last_mag_raw
        x = _twos_complement_16(data[0], data[1])
        y = _twos_complement_16(data[2], data[3])
        z = _twos_complement_16(data[4], data[5])
        scale = _MAG_SENSITIVITY_UT_PER_LSB[self._mag_fs_gauss]
        self._last_mag_raw = Vector3(x * scale, y * scale, z * scale)
        return self._last_mag_raw

    def configure_magnetometer(self, fs_gauss: int = _MAG_DEFAULT_FS_GAUSS) -> None:
        """Aktiver og konfigurer magnetometeret for kontinuerlig lesing.

        Sett magnetometeret i høy-ytelses, kontinuerlig driftsmodus.
        Kall denne metoden for å aktivere magnetometeret etter at
        konstruktøren satte det i hvilemodus.

        Args:
            fs_gauss: Fullskala i gauss. Gyldige verdier: 4, 8, 12, 16.
        """
        if fs_gauss not in _MAG_FS_BITS:
            raise ValueError(f"Ugyldig magnetometer fullskala: {fs_gauss}. Gyldige: 4, 8, 12, 16.")
        self._mag_fs_gauss = fs_gauss
        # Høy ytelse for XY-akser + standard ODR (10 Hz)
        self._bus.write_byte_data(self._mag_address, _MAG_CTRL_REG1_M, _MAG_PERF_HIGH)
        # Fullskala
        self._bus.write_byte_data(self._mag_address, _MAG_CTRL_REG2_M, _MAG_FS_BITS[fs_gauss])
        # Høy ytelse for Z-akse
        self._bus.write_byte_data(self._mag_address, _MAG_CTRL_REG4_M, _MAG_PERF_Z_HIGH)
        # Kontinuerlig driftsmodus
        self._bus.write_byte_data(self._mag_address, _MAG_CTRL_REG3_M, _MAG_MODE_CONTINUOUS)

    def _read_accel_raw_ms2(self) -> Vector3:
        """Råavlesning av akselerometeret i m/s² (uten offset-korreksjon)."""
        try:
            data = self._bus.read_block_data(self._ag_address, _OUT_X_L_XL, 6)
        except OSError as exc:
            _logger.warning("I2C-lesing av akselerometer feilet: %s — returnerer siste verdi", exc)
            return self._last_accel_raw
        x = _twos_complement_16(data[0], data[1])
        y = _twos_complement_16(data[2], data[3])
        z = _twos_complement_16(data[4], data[5])
        # mg/LSB -> g/LSB -> m/s²/LSB
        scale = _ACCEL_SENSITIVITY_MG_PER_LSB[self._accel_range] * 1e-3 * _GRAVITY_MS2
        self._last_accel_raw = Vector3(x * scale, y * scale, z * scale)
        return self._last_accel_raw

    def _read_gyro_raw_dps(self) -> Vector3:
        """Råavlesning av gyroskopet i grader/s (uten bias-korreksjon)."""
        try:
            data = self._bus.read_block_data(self._ag_address, _OUT_X_L_G, 6)
        except OSError as exc:
            _logger.warning("I2C-lesing av gyroskop feilet: %s — returnerer siste verdi", exc)
            return self._last_gyro_raw
        x = _twos_complement_16(data[0], data[1])
        y = _twos_complement_16(data[2], data[3])
        z = _twos_complement_16(data[4], data[5])
        # mdps/LSB -> dps/LSB
        scale = _GYRO_SENSITIVITY_MDPS_PER_LSB[self._gyro_range] * 1e-3
        self._last_gyro_raw = Vector3(x * scale, y * scale, z * scale)
        return self._last_gyro_raw
