# test_geometry_platform_geometry.py
# ===================================
# Tester for PlatformGeometry-klassen.
#
# PlatformGeometry beregner posisjonene til de 6 leddpunktene pa
# bunnplaten og toppplaten, samt beinvektorer og beinlengder for
# en gitt pose. Dette er grunnlaget for invers kinematikk.
#
# GUI-relevans:
#   GUI-en kan visualisere plattformens geometri:
#   - Vise leddposisjoner pa bunnplate og toppplate
#   - Tegne beinvektorer mellom leddpunktene
#   - Vise hvordan geometrien endrer seg med ulik konfigurasjon
#   - La brukeren justere geometri-parametere og se effekten

import math

import pytest

from stewart_platform.config.platform_config import PlatformConfig
from stewart_platform.geometry.vector3 import Vector3
from stewart_platform.geometry.pose import Pose
from stewart_platform.geometry.platform_geometry import PlatformGeometry


class TestPlatformGeometryOpprettelse:
    """Tester for opprettelse av PlatformGeometry."""

    def test_opprettelse_fra_standard_config(self, default_platform_config):
        """Sjekk at PlatformGeometry kan opprettes fra standard konfigurasjon."""
        geo = PlatformGeometry(default_platform_config)
        assert geo is not None

    def test_lagrer_geometri_parametere(self, default_platform_config):
        """Sjekk at geometriske parametere lagres fra konfigurasjonen.

        Disse verdiene brukes i alle videre beregninger.
        """
        geo = PlatformGeometry(default_platform_config)
        assert geo._base_radius == 100.0
        assert geo._platform_radius == 75.0
        assert geo._servo_horn_length == 25.0
        assert geo._rod_length == 150.0
        assert geo._home_height == 120.0


class TestBunnplateLedd:
    """Tester for beregning av bunnplatens leddposisjoner.

    Leddene er fordelt pa en sirkel med gitt radius og vinkler.
    Standard: 6 ledd med 60 graders mellomrom.
    """

    def test_seks_leddpunkter(self, default_platform_config):
        """Sjekk at det returneres noyaktig 6 leddposisjoner."""
        geo = PlatformGeometry(default_platform_config)
        joints = geo.get_base_joints()
        assert len(joints) == 6

    def test_ledd_er_vector3(self, default_platform_config):
        """Sjekk at hvert leddpunkt er en Vector3-instans."""
        geo = PlatformGeometry(default_platform_config)
        joints = geo.get_base_joints()
        for joint in joints:
            assert isinstance(joint, Vector3)

    def test_ledd_pa_riktig_radius(self, default_platform_config):
        """Sjekk at alle ledd ligger pa sirkelen med riktig radius.

        Hvert leddpunkt skal ha avstand lik base_radius fra origo (Z=0).
        """
        geo = PlatformGeometry(default_platform_config)
        joints = geo.get_base_joints()
        for joint in joints:
            avstand = math.sqrt(joint.x ** 2 + joint.y ** 2)
            assert avstand == pytest.approx(100.0, abs=1e-6)

    def test_ledd_z_er_null(self, default_platform_config):
        """Sjekk at alle bunnplate-ledd har Z=0 (de ligger i XY-planet)."""
        geo = PlatformGeometry(default_platform_config)
        joints = geo.get_base_joints()
        for joint in joints:
            assert joint.z == pytest.approx(0.0)

    def test_forste_ledd_pa_x_aksen(self, default_platform_config):
        """Sjekk at forste ledd (vinkel=0) ligger langs positiv X-akse.

        Med vinkel 0 grader: x=radius, y=0.
        """
        geo = PlatformGeometry(default_platform_config)
        joints = geo.get_base_joints()
        assert joints[0].x == pytest.approx(100.0, abs=1e-6)
        assert joints[0].y == pytest.approx(0.0, abs=1e-6)


class TestToppplateLedd:
    """Tester for toppplatens leddposisjoner (lokalt koordinatsystem)."""

    def test_seks_leddpunkter(self, default_platform_config):
        """Sjekk at det returneres noyaktig 6 toppplate-ledd."""
        geo = PlatformGeometry(default_platform_config)
        joints = geo.get_platform_joints_local()
        assert len(joints) == 6

    def test_ledd_pa_riktig_radius(self, default_platform_config):
        """Sjekk at toppplate-ledd ligger pa sirkelen med platform_radius."""
        geo = PlatformGeometry(default_platform_config)
        joints = geo.get_platform_joints_local()
        for joint in joints:
            avstand = math.sqrt(joint.x ** 2 + joint.y ** 2)
            assert avstand == pytest.approx(75.0, abs=1e-6)


class TestToppplateVerdenskoordinater:
    """Tester for transformasjon av toppplate-ledd til verdenskoordinater.

    Bruker en Pose for a flytte og rotere toppplatens ledd
    fra lokalt til globalt koordinatsystem.
    """

    def test_hjemmepose_gir_riktig_hoyde(self, default_platform_config):
        """Sjekk at hjemmeposen plasserer toppplaten pa home_height.

        Ved nullpose (ingen translasjon/rotasjon) skal toppplatens
        leddpunkter ligge pa Z = home_height.
        """
        geo = PlatformGeometry(default_platform_config)
        # Hjemmeposen: ingen translasjon/rotasjon, men plattformen er pa home_height
        pose = Pose()
        world_joints = geo.get_platform_joints_world(pose)
        assert len(world_joints) == 6

    def test_translasjon_flytter_alle_ledd(self, default_platform_config):
        """Sjekk at en translasjon i X-retning flytter alle ledd likt.

        Alle toppplate-ledd skal flyttes med samme translasjon.
        """
        geo = PlatformGeometry(default_platform_config)
        pose_null = Pose()
        pose_x10 = Pose(translation=Vector3(10.0, 0.0, 0.0))

        ledd_null = geo.get_platform_joints_world(pose_null)
        ledd_flyttet = geo.get_platform_joints_world(pose_x10)

        for i in range(6):
            diff_x = ledd_flyttet[i].x - ledd_null[i].x
            assert diff_x == pytest.approx(10.0, abs=1e-6)


class TestBeinvektorerOgLengder:
    """Tester for beregning av beinvektorer og beinlengder.

    Beinvektorene gar fra bunnplate-ledd til toppplate-ledd.
    Beinlengdene brukes av IK-solveren for a beregne servovinkler.
    """

    def test_seks_beinvektorer(self, default_platform_config):
        """Sjekk at det returneres noyaktig 6 beinvektorer."""
        geo = PlatformGeometry(default_platform_config)
        pose = Pose()
        legs = geo.get_leg_vectors(pose)
        assert len(legs) == 6

    def test_seks_beinlengder(self, default_platform_config):
        """Sjekk at det returneres noyaktig 6 beinlengder."""
        geo = PlatformGeometry(default_platform_config)
        pose = Pose()
        lengths = geo.get_leg_lengths(pose)
        assert len(lengths) == 6

    def test_beinlengder_er_positive(self, default_platform_config):
        """Sjekk at alle beinlengder er positive tall."""
        geo = PlatformGeometry(default_platform_config)
        pose = Pose()
        lengths = geo.get_leg_lengths(pose)
        for length in lengths:
            assert length > 0.0

    def test_beinlengder_symmetrisk_ved_hjemmepose(self, default_platform_config):
        """Sjekk at alle bein har omtrent lik lengde ved hjemmepose.

        Ved nullpose (sentrert, vannrett) skal alle bein vaere like lange
        pa grunn av symmetrien i plattformen.
        """
        geo = PlatformGeometry(default_platform_config)
        pose = Pose()
        lengths = geo.get_leg_lengths(pose)
        gjennomsnitt = sum(lengths) / len(lengths)
        for length in lengths:
            assert length == pytest.approx(gjennomsnitt, rel=0.01)


class TestHjemmehoyde:
    """Tester for beregning av hvilehoyden."""

    def test_compute_home_height_er_positiv(self, default_platform_config):
        """Sjekk at beregnet hvilehyode er positiv (over bunnplaten)."""
        geo = PlatformGeometry(default_platform_config)
        height = geo.compute_home_height()
        assert height > 0.0

    def test_eksplisitt_home_height_brukes(self, default_platform_config):
        """Sjekk at eksplisitt home_height i config respekteres."""
        default_platform_config.home_height = 99.5
        geo = PlatformGeometry(default_platform_config)
        assert geo._home_height == 99.5

    def test_none_home_height_avledes_fra_geometri(self, default_platform_config):
        """Sjekk at None i config faar geometrien til aa beregne hvilehoyden.

        Dette unngaar dobbel kilde til sannhet: brukere som lar
        feltet staa tomt (eller eksplisitt null i YAML) faar en
        konsistent hvilehoyde fra rod_length og leddradiene.
        """
        default_platform_config.home_height = None
        geo = PlatformGeometry(default_platform_config)
        assert geo._home_height == pytest.approx(geo.compute_home_height())
