# test_geometry_vector3.py
# ========================
# Tester for Vector3-klassen.
#
# Vector3 er den grunnleggende byggeklossen for all geometri i systemet.
# Den brukes til posisjoner (mm), akselerasjon (m/s^2), vinkelhastighet
# (grader/s) og retningsvektorer. Korrekt aritmetikk er kritisk for
# at kinematikk og kontrollsystemet fungerer.
#
# GUI-relevans:
#   GUI-en viser IMU-data som Vector3 (akselerasjon, gyroskop),
#   og orientering som Vector3 (roll, pitch, yaw). Riktig konvertering
#   til/fra numpy arrays er viktig for visualisering.

import math

import numpy as np
import pytest

from stewart_platform.geometry.vector3 import Vector3


class TestVector3Opprettelse:
    """Tester for opprettelse av Vector3-objekter."""

    def test_standardverdier_er_null(self):
        """Sjekk at en Vector3 uten argumenter gir nullvektor (0, 0, 0)."""
        v = Vector3()
        assert v.x == 0.0
        assert v.y == 0.0
        assert v.z == 0.0

    def test_egendefinerte_verdier(self):
        """Sjekk at x, y, z settes korrekt ved opprettelse."""
        v = Vector3(1.0, 2.0, 3.0)
        assert v.x == 1.0
        assert v.y == 2.0
        assert v.z == 3.0

    def test_negative_verdier(self):
        """Sjekk at negative verdier handteres korrekt."""
        v = Vector3(-5.0, -10.0, -15.0)
        assert v.x == -5.0
        assert v.y == -10.0
        assert v.z == -15.0


class TestVector3Aritmetikk:
    """Tester for vektoraritmetikk (addisjon, subtraksjon, skalering).

    Korrekt aritmetikk er nodvendig for:
    - Beregning av beinvektorer (subtraksjon av posisjoner)
    - Skalering av PID-korreksjon
    - Kombinering av IMU-data
    """

    def test_addisjon(self):
        """Sjekk at to vektorer adderes komponentvis: (1,2,3) + (4,5,6) = (5,7,9)."""
        a = Vector3(1.0, 2.0, 3.0)
        b = Vector3(4.0, 5.0, 6.0)
        result = a + b
        assert result.x == pytest.approx(5.0)
        assert result.y == pytest.approx(7.0)
        assert result.z == pytest.approx(9.0)

    def test_addisjon_endrer_ikke_originaler(self):
        """Sjekk at addisjon returnerer en ny vektor uten a endre de opprinnelige."""
        a = Vector3(1.0, 2.0, 3.0)
        b = Vector3(4.0, 5.0, 6.0)
        _ = a + b
        assert a.x == 1.0
        assert b.x == 4.0

    def test_subtraksjon(self):
        """Sjekk at vektorer subtraheres komponentvis: (5,7,9) - (4,5,6) = (1,2,3)."""
        a = Vector3(5.0, 7.0, 9.0)
        b = Vector3(4.0, 5.0, 6.0)
        result = a - b
        assert result.x == pytest.approx(1.0)
        assert result.y == pytest.approx(2.0)
        assert result.z == pytest.approx(3.0)

    def test_skalarmultiplikasjon(self):
        """Sjekk at skalar * vektor skalerer alle komponenter: (1,2,3) * 3 = (3,6,9)."""
        v = Vector3(1.0, 2.0, 3.0)
        result = v * 3.0
        assert result.x == pytest.approx(3.0)
        assert result.y == pytest.approx(6.0)
        assert result.z == pytest.approx(9.0)

    def test_skalarmultiplikasjon_med_null(self):
        """Sjekk at multiplikasjon med 0 gir nullvektor."""
        v = Vector3(5.0, 10.0, 15.0)
        result = v * 0.0
        assert result.x == pytest.approx(0.0)
        assert result.y == pytest.approx(0.0)
        assert result.z == pytest.approx(0.0)

    def test_negering(self):
        """Sjekk at negering inverterer alle komponenter: -(1,2,3) = (-1,-2,-3)."""
        v = Vector3(1.0, 2.0, 3.0)
        result = -v
        assert result.x == pytest.approx(-1.0)
        assert result.y == pytest.approx(-2.0)
        assert result.z == pytest.approx(-3.0)


class TestVector3Geometri:
    """Tester for geometriske operasjoner (lengde, normalisering, dot, cross).

    Disse operasjonene brukes i:
    - Beinlengdeberegning (magnitude)
    - Retningsberegning (normalized)
    - Vinkelberegning mellom vektorer (dot)
    - Rotasjonsakse-beregning (cross)
    """

    def test_magnitude_enhetsvektor(self):
        """Sjekk at en enhetsvektor langs X har lengde 1."""
        v = Vector3(1.0, 0.0, 0.0)
        assert v.magnitude() == pytest.approx(1.0)

    def test_magnitude_3d(self):
        """Sjekk at lengden av (3, 4, 0) er 5 (Pythagoras)."""
        v = Vector3(3.0, 4.0, 0.0)
        assert v.magnitude() == pytest.approx(5.0)

    def test_magnitude_full_3d(self):
        """Sjekk at lengden av (1, 2, 2) er 3: sqrt(1+4+4) = 3."""
        v = Vector3(1.0, 2.0, 2.0)
        assert v.magnitude() == pytest.approx(3.0)

    def test_magnitude_nullvektor(self):
        """Sjekk at nullvektoren har lengde 0."""
        v = Vector3(0.0, 0.0, 0.0)
        assert v.magnitude() == pytest.approx(0.0)

    def test_normalized_enhetsvektor(self):
        """Sjekk at en normalisert vektor har lengde 1."""
        v = Vector3(3.0, 4.0, 0.0)
        n = v.normalized()
        assert n.magnitude() == pytest.approx(1.0)

    def test_normalized_retning(self):
        """Sjekk at normalisering bevarer retningen: (0,0,5).normalized = (0,0,1)."""
        v = Vector3(0.0, 0.0, 5.0)
        n = v.normalized()
        assert n.x == pytest.approx(0.0)
        assert n.y == pytest.approx(0.0)
        assert n.z == pytest.approx(1.0)

    def test_normalized_nullvektor_feiler(self):
        """Sjekk at normalisering av nullvektor kaster ValueError.

        En nullvektor har ingen retning og kan ikke normaliseres.
        """
        v = Vector3(0.0, 0.0, 0.0)
        with pytest.raises(ValueError):
            v.normalized()

    def test_dot_product_parallelle(self):
        """Sjekk at prikkproduktet av parallelle enhetsvektorer er 1."""
        a = Vector3(1.0, 0.0, 0.0)
        b = Vector3(1.0, 0.0, 0.0)
        assert a.dot(b) == pytest.approx(1.0)

    def test_dot_product_vinkelrette(self):
        """Sjekk at prikkproduktet av vinkelrette vektorer er 0."""
        a = Vector3(1.0, 0.0, 0.0)
        b = Vector3(0.0, 1.0, 0.0)
        assert a.dot(b) == pytest.approx(0.0)

    def test_dot_product_generelt(self):
        """Sjekk generelt prikkprodukt: (1,2,3).(4,5,6) = 4+10+18 = 32."""
        a = Vector3(1.0, 2.0, 3.0)
        b = Vector3(4.0, 5.0, 6.0)
        assert a.dot(b) == pytest.approx(32.0)

    def test_cross_product_x_cross_y(self):
        """Sjekk at X x Y = Z (hoyrehandsregelen)."""
        x = Vector3(1.0, 0.0, 0.0)
        y = Vector3(0.0, 1.0, 0.0)
        result = x.cross(y)
        assert result.x == pytest.approx(0.0)
        assert result.y == pytest.approx(0.0)
        assert result.z == pytest.approx(1.0)

    def test_cross_product_parallelle_er_null(self):
        """Sjekk at kryssproduktet av parallelle vektorer er nullvektor."""
        a = Vector3(2.0, 0.0, 0.0)
        b = Vector3(5.0, 0.0, 0.0)
        result = a.cross(b)
        assert result.x == pytest.approx(0.0)
        assert result.y == pytest.approx(0.0)
        assert result.z == pytest.approx(0.0)

    def test_cross_product_antikommutativ(self):
        """Sjekk at A x B = -(B x A) (antikommutativitet)."""
        a = Vector3(1.0, 2.0, 3.0)
        b = Vector3(4.0, 5.0, 6.0)
        ab = a.cross(b)
        ba = b.cross(a)
        assert ab.x == pytest.approx(-ba.x)
        assert ab.y == pytest.approx(-ba.y)
        assert ab.z == pytest.approx(-ba.z)


class TestVector3Konvertering:
    """Tester for konvertering mellom Vector3 og numpy array.

    GUI-en og visualiseringskode bruker numpy arrays internt,
    sa konvertering ma vaere korrekt og tapsfri.
    """

    def test_to_array(self):
        """Sjekk at to_array gir korrekt numpy array [x, y, z]."""
        v = Vector3(1.0, 2.0, 3.0)
        arr = v.to_array()
        assert isinstance(arr, np.ndarray)
        assert len(arr) == 3
        assert arr[0] == pytest.approx(1.0)
        assert arr[1] == pytest.approx(2.0)
        assert arr[2] == pytest.approx(3.0)

    def test_from_array(self):
        """Sjekk at from_array oppretter korrekt Vector3 fra numpy array."""
        arr = np.array([4.0, 5.0, 6.0])
        v = Vector3.from_array(arr)
        assert v.x == pytest.approx(4.0)
        assert v.y == pytest.approx(5.0)
        assert v.z == pytest.approx(6.0)

    def test_roundtrip_to_from_array(self):
        """Sjekk at Vector3 -> array -> Vector3 gir identisk resultat."""
        original = Vector3(7.7, 8.8, 9.9)
        arr = original.to_array()
        restored = Vector3.from_array(arr)
        assert restored.x == pytest.approx(original.x)
        assert restored.y == pytest.approx(original.y)
        assert restored.z == pytest.approx(original.z)

    def test_repr(self):
        """Sjekk at __repr__ gir lesbar tekstrepresentasjon."""
        v = Vector3(1.0, 2.0, 3.0)
        text = repr(v)
        assert "Vector3" in text
        assert "1.0" in text
