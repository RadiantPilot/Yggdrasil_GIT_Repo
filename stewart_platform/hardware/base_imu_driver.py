# base_imu_driver.py
# ==================
# Driver for IMU-sensoren på bunnplaten.
# Implementerer IMUInterface slik at den kan byttes ut med en
# annen sensortype uten å endre resten av systemet.
# Bunnplate-IMUen brukes som referanse for å kompensere for
# bevegelse av selve basen (f.eks. hvis plattformen er montert
# på et bevegelig underlag).

from __future__ import annotations

from ..geometry.vector3 import Vector3
from .i2c_bus import I2CBus
from .imu_interface import IMUInterface


class BaseIMUDriver(IMUInterface):
    """Driver for bunnplatens IMU-sensor.

    Gir akselerometer- og gyroskopdata for bunnplaten.
    Brukes som referanseramme for å kunne kompensere for
    bevegelse i basen. Implementerer IMUInterface slik at
    MotionController kan behandle den likt som toppplate-IMUen.

    Denne driveren kan tilpasses til den spesifikke IMU-chipen
    som brukes på bunnplaten (f.eks. en annen LSM6DSOX, MPU6050,
    eller RPi Sense HAT IMU).
    """

    def __init__(self, bus: I2CBus, address: int) -> None:
        """Opprett en ny bunnplate-IMU-driver.

        Args:
            bus: I2C-bussinstans for kommunikasjon.
            address: I2C-adresse for sensoren.
        """
        self._bus = bus
        self._address = address

    def configure(self, **kwargs) -> None:
        """Konfigurer sensorens innstillinger.

        Spesifikke parametere avhenger av hvilken IMU-chip
        som er montert på bunnplaten.

        Args:
            **kwargs: Sensorspesifikke konfigurasjonsparametere.
        """
        raise NotImplementedError

    def read_acceleration(self) -> Vector3:
        """Les akselerasjonsdata fra bunnplatens sensor.

        Returns:
            Vector3 med akselerasjon i m/s² for X, Y og Z-aksen.
        """
        raise NotImplementedError

    def read_gyroscope(self) -> Vector3:
        """Les gyroskopdata fra bunnplatens sensor.

        Returns:
            Vector3 med vinkelhastighet i grader/s for X, Y og Z-aksen.
        """
        raise NotImplementedError

    def read_temperature(self) -> float:
        """Les temperaturen fra sensorens termometer.

        Returns:
            Temperatur i grader Celsius.
        """
        raise NotImplementedError

    def who_am_i(self) -> int:
        """Les sensorens identifikasjonsregister.

        Returns:
            Enhets-ID for verifisering av korrekt sensor.
        """
        raise NotImplementedError

    def reset(self) -> None:
        """Tilbakestill sensoren til standardinnstillinger."""
        raise NotImplementedError
