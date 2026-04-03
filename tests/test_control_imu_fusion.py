# test_control_imu_fusion.py
# ===========================
# Tester for IMUFusion-klassen (komplementaerfilter).
#
# IMUFusion kombinerer akselerometer- og gyroskopdata for a
# estimere plattformens orientering (roll, pitch, yaw).
# Akselerometeret gir langsiktig stabilitet, gyroskopet gir
# rask respons. Filteret balanserer disse via alpha-parameteren.
#
# GUI-relevans:
#   GUI-en viser orientering fra IMU-fusjon i sanntid.
#   Alpha-parameteren kan justeres for a se effekten pa
#   filtreringen (mer/mindre glatting).

import pytest

from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.control.imu_fusion import IMUFusion


@pytest.fixture
def fusion():
    """Standard IMUFusion med alpha=0.98."""
    return IMUFusion(alpha=0.98)


class TestIMUFusionOpprettelse:
    """Tester for opprettelse av IMUFusion."""

    def test_opprettelse_standard(self):
        """Sjekk at IMUFusion kan opprettes med standard alpha."""
        f = IMUFusion()
        assert f._alpha == 0.98

    def test_opprettelse_egendefinert_alpha(self):
        """Sjekk at alpha kan overstyres.

        Lavere alpha gir mer vekt pa akselerometeret (tregere, mer stabilt).
        Hoyere alpha gir mer vekt pa gyroskopet (raskere, mer drift).
        """
        f = IMUFusion(alpha=0.95)
        assert f._alpha == 0.95

    def test_startorientering_er_null(self, fusion):
        """Sjekk at orienteringen starter pa (0, 0, 0)."""
        o = fusion.get_orientation()
        assert o.x == 0.0
        assert o.y == 0.0
        assert o.z == 0.0


class TestIMUFusionUpdate:
    """Tester for oppdatering av orienteringsestimat."""

    def test_update_returnerer_vector3(self, fusion):
        """Sjekk at update() returnerer en Vector3 med orientering."""
        accel = Vector3(0.0, 0.0, 9.81)  # Rett ned = ingen tilt
        gyro = Vector3(0.0, 0.0, 0.0)    # Ingen rotasjon
        result = fusion.update(accel, gyro, dt=0.02)
        assert isinstance(result, Vector3)

    def test_flat_orientering_ved_gravitasjon_i_z(self, fusion):
        """Sjekk at gravitasjon rett ned (Z=9.81) gir flat orientering.

        Nar akselerometeret maler ren gravitasjon i Z-retning,
        betyr det at plattformen er helt vannrett (roll=0, pitch=0).
        """
        accel = Vector3(0.0, 0.0, 9.81)
        gyro = Vector3(0.0, 0.0, 0.0)
        # Kjor flere iterasjoner for a la filteret stabilisere seg
        for _ in range(100):
            fusion.update(accel, gyro, dt=0.02)
        o = fusion.get_orientation()
        assert o.x == pytest.approx(0.0, abs=2.0)  # roll ~ 0
        assert o.y == pytest.approx(0.0, abs=2.0)  # pitch ~ 0

    def test_akselerometer_tilt_gir_roll(self, fusion):
        """Sjekk at tilt i akselerometerdata gir roll-utslag.

        Nar gravitasjonen har en Y-komponent, er plattformen tiltet
        rundt X-aksen (roll).
        """
        # Tilt: gravitasjon har komponent i Y-retning
        accel = Vector3(0.0, 5.0, 8.5)  # Tiltet rundt X-aksen
        gyro = Vector3(0.0, 0.0, 0.0)
        for _ in range(200):
            fusion.update(accel, gyro, dt=0.02)
        o = fusion.get_orientation()
        # Roll skal vaere merkbart ikke-null
        assert abs(o.x) > 5.0

    def test_gyroskop_integrerer_over_tid(self):
        """Sjekk at gyroskopdata integreres til orientering over tid.

        Ren gyroskopintegrasjon (alpha=1.0) skal gi
        orientering = forrige + gyro * dt.
        """
        f = IMUFusion(alpha=1.0)  # Kun gyroskop, ingen akselerometer
        accel = Vector3(0.0, 0.0, 9.81)
        gyro = Vector3(10.0, 0.0, 0.0)  # 10 grader/s rundt X-aksen
        # 100 iterasjoner * 0.02s * 10 grader/s = 20 grader
        for _ in range(100):
            f.update(accel, gyro, dt=0.02)
        o = f.get_orientation()
        assert o.x == pytest.approx(20.0, abs=2.0)


class TestIMUFusionGetOrientation:
    """Tester for henting av naavaerende orientering.

    GUI-en poller get_orientation() for a vise sanntidsorientering.
    """

    def test_get_orientation_uten_update(self, fusion):
        """Sjekk at get_orientation() fungerer for forste update."""
        o = fusion.get_orientation()
        assert isinstance(o, Vector3)

    def test_get_orientation_etter_update(self, fusion):
        """Sjekk at get_orientation() reflekterer siste update."""
        fusion.update(Vector3(0.0, 0.0, 9.81), Vector3(0.0, 0.0, 0.0), 0.02)
        o = fusion.get_orientation()
        assert isinstance(o, Vector3)


class TestIMUFusionReset:
    """Tester for nullstilling av IMUFusion."""

    def test_reset_nullstiller_orientering(self, fusion):
        """Sjekk at reset() setter orienteringen tilbake til (0, 0, 0).

        Brukes etter rekalibrering eller nodstopp.
        """
        fusion.update(Vector3(0.0, 5.0, 8.5), Vector3(10.0, 0.0, 0.0), 0.02)
        fusion.reset()
        o = fusion.get_orientation()
        assert o.x == 0.0
        assert o.y == 0.0
        assert o.z == 0.0
