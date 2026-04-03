# imu_fusion.py
# =============
# Sensorfusjon for IMU-data.
# Kombinerer akselerometer- og gyroskopdata ved hjelp av et
# komplementærfilter for å estimere en stabil orientering.
# Akselerometeret gir langsiktig nøyaktighet, mens gyroskopet
# gir kortsiktig presisjon. Filteret balanserer disse to.

from __future__ import annotations

from ..geometry.vector3 import Vector3


class IMUFusion:
    """Komplementærfilter for IMU-sensorfusjon.

    Kombinerer data fra akselerometer og gyroskop for å gi et
    stabilt orienteringsestimat. Akselerometeret er nøyaktig
    over tid men følsomt for vibrasjoner, mens gyroskopet er
    raskt men driver over tid. Komplementærfilteret balanserer
    disse egenskapene.

    Formel: vinkel = alpha * (vinkel + gyro * dt) + (1 - alpha) * accel_vinkel

    alpha-verdien bestemmer vektingen:
    - alpha nær 1.0: Stoler mer på gyroskopet (raskere respons, mer drift).
    - alpha nær 0.0: Stoler mer på akselerometeret (tregere, men stabil).
    - Typisk verdi: 0.96 - 0.98.
    """

    def __init__(self, alpha: float = 0.98) -> None:
        """Opprett et nytt komplementærfilter.

        Args:
            alpha: Filtervekting mellom 0 og 1.
                   Høyere verdi = mer gyroskopvekting.
        """
        self._alpha = alpha
        self._current_orientation = Vector3()
        self._last_time = 0.0

    def update(self, accel: Vector3, gyro: Vector3, dt: float) -> Vector3:
        """Oppdater orienteringsestimatet med nye sensordata.

        Beregner roll og pitch fra akselerometeret (via atan2),
        integrerer gyroskopdata, og kombinerer med komplementærfilteret.

        Args:
            accel: Akselerasjonsdata i m/s² (X, Y, Z).
            gyro: Gyroskopdata i grader/s (X, Y, Z).
            dt: Tid siden forrige oppdatering i sekunder.

        Returns:
            Oppdatert orientering som Vector3 (roll, pitch, yaw) i grader.
        """
        raise NotImplementedError

    def get_orientation(self) -> Vector3:
        """Hent nåværende estimert orientering.

        Returns:
            Vector3 med (roll, pitch, yaw) i grader.
        """
        return self._current_orientation

    def reset(self) -> None:
        """Nullstill orienteringsestimatet til (0, 0, 0).

        Bør kalles ved oppstart eller etter rekalibrering.
        """
        self._current_orientation = Vector3()
        self._last_time = 0.0
