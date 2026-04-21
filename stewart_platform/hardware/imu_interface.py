# imu_interface.py
# ================
# Abstrakt grensesnitt for IMU-sensorer (Inertial Measurement Unit).
# Definerer en felles kontrakt som alle IMU-drivere må implementere.
# Dette gjør det mulig å bytte IMU-type uten å endre resten av systemet.

from __future__ import annotations

from abc import ABC, abstractmethod

from ..geometry.vector3 import Vector3


class IMUInterface(ABC):
    """Abstrakt baseklasse for IMU-sensorer.

    Alle IMU-drivere (f.eks. LSM6DSOXTR) må implementere dette
    grensesnittet. Dette sikrer at MotionController og IMUFusion
    kan bruke hvilken som helst IMU-type uten kodeendringer.
    """

    @abstractmethod
    def configure(self, **kwargs) -> None:
        """Konfigurer IMU-sensorens innstillinger.

        Innstillinger kan inkludere akselerometerområde, gyroskopområde,
        datahastighet og filtre. Konkrete parametere avhenger av
        den spesifikke IMU-chipen.

        Args:
            **kwargs: Sensorspesifikke konfigurasjonsparametere.
        """
        ...

    @abstractmethod
    def read_acceleration(self) -> Vector3:
        """Les akselerasjonsdata fra sensoren.

        Returns:
            Vector3 med akselerasjon i m/s² for X, Y og Z-aksen.
        """
        ...

    @abstractmethod
    def read_angular_velocity(self) -> Vector3:
        """Les gyroskopdata fra sensoren.

        Returns:
            Vector3 med vinkelhastighet i grader/s for X, Y og Z-aksen.
        """
        ...

    @abstractmethod
    def read_temperature(self) -> float:
        """Les temperaturen fra sensorens innebygde termometer.

        Returns:
            Temperatur i grader Celsius.
        """
        ...

    @abstractmethod
    def who_am_i(self) -> int:
        """Les sensorens identifikasjonsregister.

        Brukes for å verifisere at riktig sensor er tilkoblet.

        Returns:
            Enhets-ID som en heltallsverdi.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Tilbakestill sensoren til fabrikkinnstillinger.

        Nyttig ved oppstart eller etter en feilsituasjon.
        """
        ...

    @abstractmethod
    def calibrate_gyro_bias(self) -> None:
        """Kalibrer gyroskopets nullpunktsfeil (bias).

        Leser et antall samples mens sensoren er i ro og
        beregner gjennomsnittlig offset for hver akse.
        Etterfølgende avlesninger kompenseres automatisk.
        """
        ...

    @abstractmethod
    def calibrate_accelerometer_offset(self) -> None:
        """Kalibrer akselerometerets offset.

        Leser et antall samples mens sensoren er i ro og
        vannrett, og beregner offset slik at Z-aksen viser
        nøyaktig 1g og X/Y viser 0.
        """
        ...
