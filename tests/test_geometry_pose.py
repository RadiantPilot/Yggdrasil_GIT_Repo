# test_geometry_pose.py
# =====================
# Tester for Pose-klassen.
#
# Pose representerer toppplatens 6-DOF tilstand: posisjon (X, Y, Z)
# og orientering (roll, pitch, yaw). Dette er den sentrale datatypen
# som flyter gjennom hele systemet — fra mal-pose via IK til servoer.
#
# GUI-relevans:
#   GUI-en viser naavaerende og mal-pose, og lar brukeren sette mal-pose
#   via sliders for X, Y, Z, roll, pitch, yaw. Interpolasjon brukes
#   for jevne bevegelser. Matrise-konvertering brukes for 3D-visualisering.

import math

import numpy as np
import pytest

from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.geometry.pose import Pose


class TestPoseOpprettelse:
    """Tester for opprettelse av Pose-objekter."""

    def test_standardverdier_er_null(self):
        """Sjekk at en Pose uten argumenter gir nullpose (origo, ingen rotasjon).

        Nullposen tilsvarer toppplaten sentrert og vannrett over bunnplaten.
        """
        p = Pose()
        assert p.translation.x == 0.0
        assert p.translation.y == 0.0
        assert p.translation.z == 0.0
        assert p.rotation.x == 0.0
        assert p.rotation.y == 0.0
        assert p.rotation.z == 0.0

    def test_egendefinert_pose(self):
        """Sjekk at translasjon og rotasjon kan settes ved opprettelse."""
        p = Pose(
            translation=Vector3(10.0, 20.0, 30.0),
            rotation=Vector3(5.0, 10.0, 15.0),
        )
        assert p.translation.x == 10.0
        assert p.translation.y == 20.0
        assert p.translation.z == 30.0
        assert p.rotation.x == 5.0
        assert p.rotation.y == 10.0
        assert p.rotation.z == 15.0

    def test_home_pose(self):
        """Sjekk at Pose.home() returnerer nullpose.

        Hjemmeposen er utgangspunktet for all bevegelse.
        """
        p = Pose.home()
        assert p.translation.x == 0.0
        assert p.translation.y == 0.0
        assert p.translation.z == 0.0
        assert p.rotation.x == 0.0
        assert p.rotation.y == 0.0
        assert p.rotation.z == 0.0


class TestPoseMatrise:
    """Tester for konvertering mellom Pose og 4x4 transformasjonsmatrise.

    Matrisekonvertering er kjernen i kinematikkberegningene:
    - to_matrix() brukes av InverseKinematics for a transformere leddposisjoner
    - from_matrix() brukes for a ekstrahere pose fra beregningsresultater
    - GUI-en kan bruke matrisen for 3D-visualisering
    """

    def test_nullpose_gir_identitetsmatrise(self):
        """Sjekk at nullposen gir en 4x4 identitetsmatrise.

        Ingen translasjon + ingen rotasjon = identitetstransformasjon.
        """
        p = Pose()
        m = p.to_matrix()
        assert m.shape == (4, 4)
        np.testing.assert_array_almost_equal(m, np.eye(4))

    def test_ren_translasjon(self):
        """Sjekk at ren translasjon (ingen rotasjon) gir korrekt matrise.

        Translasjonen skal ligge i siste kolonne av matrisen: [tx, ty, tz].
        """
        p = Pose(translation=Vector3(10.0, 20.0, 30.0))
        m = p.to_matrix()
        assert m[0, 3] == pytest.approx(10.0)
        assert m[1, 3] == pytest.approx(20.0)
        assert m[2, 3] == pytest.approx(30.0)
        # Rotasjonsdelen skal vaere identitet
        np.testing.assert_array_almost_equal(m[:3, :3], np.eye(3))

    def test_ren_rotasjon_roll_90(self):
        """Sjekk at 90 graders roll roterer Y-aksen til Z-aksen.

        Roll er rotasjon rundt X-aksen. Ved 90 grader:
        Y -> Z og Z -> -Y.
        """
        p = Pose(rotation=Vector3(90.0, 0.0, 0.0))
        m = p.to_matrix()
        # Translasjonen skal vaere null
        assert m[0, 3] == pytest.approx(0.0)
        assert m[1, 3] == pytest.approx(0.0)
        assert m[2, 3] == pytest.approx(0.0)
        # Rotasjonsmatrisen for 90 grader roll
        assert m[1, 1] == pytest.approx(0.0, abs=1e-10)
        assert m[2, 2] == pytest.approx(0.0, abs=1e-10)

    def test_matrise_er_4x4(self):
        """Sjekk at matrisen alltid er 4x4 (homogene koordinater)."""
        p = Pose(
            translation=Vector3(5.0, 10.0, 15.0),
            rotation=Vector3(10.0, 20.0, 30.0),
        )
        m = p.to_matrix()
        assert m.shape == (4, 4)
        # Siste rad skal vaere [0, 0, 0, 1]
        np.testing.assert_array_almost_equal(m[3, :], [0, 0, 0, 1])

    def test_roundtrip_to_from_matrix(self):
        """Sjekk at Pose -> matrise -> Pose gir tilbake samme verdier.

        Roundtrip-test er kritisk for a sikre at informasjon
        ikke gar tapt i konverteringen.
        """
        original = Pose(
            translation=Vector3(15.0, -10.0, 25.0),
            rotation=Vector3(5.0, -8.0, 12.0),
        )
        m = original.to_matrix()
        restored = Pose.from_matrix(m)
        assert restored.translation.x == pytest.approx(original.translation.x, abs=1e-6)
        assert restored.translation.y == pytest.approx(original.translation.y, abs=1e-6)
        assert restored.translation.z == pytest.approx(original.translation.z, abs=1e-6)
        assert restored.rotation.x == pytest.approx(original.rotation.x, abs=1e-3)
        assert restored.rotation.y == pytest.approx(original.rotation.y, abs=1e-3)
        assert restored.rotation.z == pytest.approx(original.rotation.z, abs=1e-3)


class TestPoseInterpolasjon:
    """Tester for lineaer interpolasjon mellom to poser.

    Interpolasjon brukes for a generere jevne bevegelser.
    GUI-en kan bruke dette for smooth-overgang nar brukeren
    drar en slider fra en posisjon til en annen.
    """

    def test_interpolasjon_t0_gir_start(self):
        """Sjekk at t=0 gir startposen."""
        a = Pose(translation=Vector3(0.0, 0.0, 0.0))
        b = Pose(translation=Vector3(10.0, 20.0, 30.0))
        result = a.interpolate(b, 0.0)
        assert result.translation.x == pytest.approx(0.0)
        assert result.translation.y == pytest.approx(0.0)
        assert result.translation.z == pytest.approx(0.0)

    def test_interpolasjon_t1_gir_slutt(self):
        """Sjekk at t=1 gir sluttposen."""
        a = Pose(translation=Vector3(0.0, 0.0, 0.0))
        b = Pose(translation=Vector3(10.0, 20.0, 30.0))
        result = a.interpolate(b, 1.0)
        assert result.translation.x == pytest.approx(10.0)
        assert result.translation.y == pytest.approx(20.0)
        assert result.translation.z == pytest.approx(30.0)

    def test_interpolasjon_t05_gir_midtpunkt(self):
        """Sjekk at t=0.5 gir midtpunktet mellom to poser."""
        a = Pose(
            translation=Vector3(0.0, 0.0, 0.0),
            rotation=Vector3(0.0, 0.0, 0.0),
        )
        b = Pose(
            translation=Vector3(10.0, 20.0, 30.0),
            rotation=Vector3(20.0, 40.0, 60.0),
        )
        result = a.interpolate(b, 0.5)
        assert result.translation.x == pytest.approx(5.0)
        assert result.translation.y == pytest.approx(10.0)
        assert result.translation.z == pytest.approx(15.0)
        assert result.rotation.x == pytest.approx(10.0)
        assert result.rotation.y == pytest.approx(20.0)
        assert result.rotation.z == pytest.approx(30.0)


class TestPoseGrenser:
    """Tester for grensekontroll av pose.

    Brukes av SafetyMonitor og GUI for a sjekke om en pose
    er innenfor tillatte grenser for den sendes til IK-solveren.
    """

    def test_nullpose_er_innenfor_alle_grenser(self):
        """Sjekk at nullposen alltid er innenfor grensene."""
        p = Pose()
        assert p.is_within_bounds(50.0, 30.0) is True

    def test_for_stor_translasjon(self):
        """Sjekk at en pose med for stor translasjon er utenfor grensene."""
        p = Pose(translation=Vector3(100.0, 0.0, 0.0))
        assert p.is_within_bounds(50.0, 30.0) is False

    def test_for_stor_rotasjon(self):
        """Sjekk at en pose med for stor rotasjon er utenfor grensene."""
        p = Pose(rotation=Vector3(45.0, 0.0, 0.0))
        assert p.is_within_bounds(50.0, 30.0) is False

    def test_akkurat_pa_grensen_translasjon(self):
        """Sjekk at en pose noyaktig pa grensen er innenfor.

        Grenseverdien skal vaere inklusiv (<=, ikke <).
        """
        p = Pose(translation=Vector3(50.0, 0.0, 0.0))
        assert p.is_within_bounds(50.0, 30.0) is True

    def test_repr(self):
        """Sjekk at __repr__ inneholder relevant informasjon."""
        p = Pose(translation=Vector3(1.0, 2.0, 3.0))
        text = repr(p)
        assert "Pose" in text
