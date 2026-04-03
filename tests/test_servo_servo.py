# test_servo_servo.py
# ===================
# Tester for Servo og ServoArray-klassene.
#
# Servo representerer en enkelt servomotor med konfigurerbar kanal,
# pulsbredde, vinkelgrenser, retning og offset.
# ServoArray samler 6 servoer for koordinert bevegelse.
#
# GUI-relevans:
#   GUI-en skal vise naavaerende vinkel for alle 6 servoer,
#   og la brukeren teste individuelle servoer manuelt.
#   Vinkelgrenser og retning pavirker hva som er gyldig input.

from unittest.mock import MagicMock

import pytest

from stewart_platform.config.platform_config import ServoConfig
from stewart_platform.hardware.pca9685_driver import PCA9685Driver
from stewart_platform.hardware.i2c_bus import I2CBus
from stewart_platform.servo.servo import Servo
from stewart_platform.servo.servo_array import ServoArray


# ---------------------------------------------------------------------------
# Fixtures for mock-hardware (vi tester uten fysisk tilkobling)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_i2c_bus():
    """Mock I2C-buss for testing uten maskinvare."""
    return MagicMock(spec=I2CBus)


@pytest.fixture
def mock_pca9685(mock_i2c_bus):
    """Mock PCA9685-driver for testing uten maskinvare.

    Alle metoder er tilgjengelige men gjor ingenting.
    """
    driver = PCA9685Driver(mock_i2c_bus, address=0x40, frequency=50)
    driver.set_pulse_width_us = MagicMock()
    driver.set_pwm = MagicMock()
    driver.set_all_pwm = MagicMock()
    return driver


@pytest.fixture
def standard_servo(mock_pca9685):
    """En servo med standardkonfigurasjon pa kanal 0."""
    config = ServoConfig(channel=0)
    return Servo(config, mock_pca9685)


@pytest.fixture
def invertert_servo(mock_pca9685):
    """En servo med invertert retning (direction=-1)."""
    config = ServoConfig(channel=1, direction=-1)
    return Servo(config, mock_pca9685)


# ===========================================================================
# Servo — Enkelt servo
# ===========================================================================

class TestServoOpprettelse:
    """Tester for opprettelse av Servo-objekter."""

    def test_opprettelse_med_standard_config(self, mock_pca9685):
        """Sjekk at en servo kan opprettes med standardkonfigurasjon."""
        config = ServoConfig(channel=0)
        servo = Servo(config, mock_pca9685)
        assert servo is not None

    def test_startvinkel_er_hjemmevinkel(self, standard_servo):
        """Sjekk at servoen starter pa hjemmevinkelen (90 grader).

        Ved oppstart skal servoen vaere i naytral posisjon.
        """
        assert standard_servo.get_angle() == 90.0


class TestServoVinkler:
    """Tester for vinkelstilling og grensekontroll.

    GUI-en viser naavaerende vinkel og bruker is_within_limits()
    for a vise om en kommandert vinkel er gyldig.
    """

    def test_set_angle_innenfor_grenser(self, standard_servo):
        """Sjekk at set_angle aksepterer en vinkel innenfor grensene."""
        standard_servo.set_angle(45.0)
        assert standard_servo.get_angle() == pytest.approx(45.0)

    def test_set_angle_til_minimum(self, standard_servo):
        """Sjekk at servoen kan settes til minimumsvinkelen."""
        standard_servo.set_angle(0.0)
        assert standard_servo.get_angle() == pytest.approx(0.0)

    def test_set_angle_til_maksimum(self, standard_servo):
        """Sjekk at servoen kan settes til maksimumsvinkelen."""
        standard_servo.set_angle(180.0)
        assert standard_servo.get_angle() == pytest.approx(180.0)

    def test_is_within_limits_gyldig(self, standard_servo):
        """Sjekk at is_within_limits returnerer True for gyldige vinkler."""
        assert standard_servo.is_within_limits(0.0) is True
        assert standard_servo.is_within_limits(90.0) is True
        assert standard_servo.is_within_limits(180.0) is True

    def test_is_within_limits_for_lav(self, standard_servo):
        """Sjekk at is_within_limits returnerer False for vinkler under minimum."""
        assert standard_servo.is_within_limits(-10.0) is False

    def test_is_within_limits_for_hoy(self, standard_servo):
        """Sjekk at is_within_limits returnerer False for vinkler over maksimum."""
        assert standard_servo.is_within_limits(190.0) is False

    def test_is_within_limits_med_egne_grenser(self, mock_pca9685):
        """Sjekk at egendefinerte vinkelgrenser respekteres.

        En servo med begrenset bevegelsesomrade (30-150 grader).
        """
        config = ServoConfig(channel=0, min_angle_deg=30.0, max_angle_deg=150.0)
        servo = Servo(config, mock_pca9685)
        assert servo.is_within_limits(29.0) is False
        assert servo.is_within_limits(30.0) is True
        assert servo.is_within_limits(150.0) is True
        assert servo.is_within_limits(151.0) is False


class TestServoPulsbredde:
    """Tester for konvertering mellom vinkel og pulsbredde.

    Pulsbredden er det faktiske PWM-signalet som sendes til servoen.
    Korrekt konvertering er kritisk for presis posisjonering.
    """

    def test_minimum_vinkel_gir_minimum_puls(self, standard_servo):
        """Sjekk at min_angle (0 grader) gir min_pulse (500 us)."""
        pulse = standard_servo.angle_to_pulse_us(0.0)
        assert pulse == 500

    def test_maksimum_vinkel_gir_maksimum_puls(self, standard_servo):
        """Sjekk at max_angle (180 grader) gir max_pulse (2500 us)."""
        pulse = standard_servo.angle_to_pulse_us(180.0)
        assert pulse == 2500

    def test_midtvinkel_gir_midtpuls(self, standard_servo):
        """Sjekk at 90 grader gir midtpunktet mellom min og max puls: 1500 us."""
        pulse = standard_servo.angle_to_pulse_us(90.0)
        assert pulse == pytest.approx(1500, abs=1)


class TestServoHjemmeposisjon:
    """Tester for hjemmeposisjon-funksjonalitet."""

    def test_go_home(self, standard_servo):
        """Sjekk at go_home setter servoen tilbake til hjemmevinkelen.

        Etter en manuell bevegelse skal go_home() returnere til 90 grader.
        """
        standard_servo.set_angle(45.0)
        standard_servo.go_home()
        assert standard_servo.get_angle() == pytest.approx(90.0)


# ===========================================================================
# ServoArray — Samling av 6 servoer
# ===========================================================================

class TestServoArrayOpprettelse:
    """Tester for opprettelse av ServoArray."""

    def test_opprettelse_med_seks_servoer(self, mock_pca9685, six_servo_configs):
        """Sjekk at en ServoArray opprettes med 6 servoer."""
        array = ServoArray(six_servo_configs, mock_pca9685)
        assert array is not None

    def test_index_tilgang(self, mock_pca9685, six_servo_configs):
        """Sjekk at individuelle servoer kan nas via indeks.

        GUI-en bruker dette for a vise/styre enkelservoer.
        """
        array = ServoArray(six_servo_configs, mock_pca9685)
        servo = array[0]
        assert isinstance(servo, Servo)

    def test_index_out_of_range(self, mock_pca9685, six_servo_configs):
        """Sjekk at ugyldig indeks kaster IndexError."""
        array = ServoArray(six_servo_configs, mock_pca9685)
        with pytest.raises(IndexError):
            _ = array[6]


class TestServoArrayBevegelse:
    """Tester for koordinert bevegelse av alle 6 servoer."""

    def test_set_angles_seks_vinkler(self, mock_pca9685, six_servo_configs):
        """Sjekk at set_angles setter alle 6 servoer til gitte vinkler.

        IK-solveren gir 6 vinkler som skal settes simultant.
        """
        array = ServoArray(six_servo_configs, mock_pca9685)
        vinkler = [80.0, 85.0, 90.0, 95.0, 100.0, 105.0]
        array.set_angles(vinkler)
        resultat = array.get_angles()
        for i in range(6):
            assert resultat[i] == pytest.approx(vinkler[i])

    def test_get_angles_returnerer_seks_verdier(self, mock_pca9685, six_servo_configs):
        """Sjekk at get_angles returnerer en liste med 6 vinkler.

        GUI-en viser alle 6 vinkler i en oversikt.
        """
        array = ServoArray(six_servo_configs, mock_pca9685)
        vinkler = array.get_angles()
        assert len(vinkler) == 6

    def test_go_home_alle(self, mock_pca9685, six_servo_configs):
        """Sjekk at go_home setter alle servoer tilbake til hjemmeposisjon."""
        array = ServoArray(six_servo_configs, mock_pca9685)
        array.set_angles([45.0, 50.0, 55.0, 60.0, 65.0, 70.0])
        array.go_home()
        vinkler = array.get_angles()
        for vinkel in vinkler:
            assert vinkel == pytest.approx(90.0)

    def test_validate_angles_gyldige(self, mock_pca9685, six_servo_configs):
        """Sjekk at validate_angles godkjenner gyldige vinkler."""
        array = ServoArray(six_servo_configs, mock_pca9685)
        assert array.validate_angles([90.0] * 6) is True

    def test_validate_angles_ugyldige(self, mock_pca9685, six_servo_configs):
        """Sjekk at validate_angles avviser vinkler utenfor grensene."""
        array = ServoArray(six_servo_configs, mock_pca9685)
        ugyldige = [90.0, 90.0, 90.0, 90.0, 90.0, 200.0]  # Siste er over 180
        assert array.validate_angles(ugyldige) is False

    def test_validate_angles_feil_antall(self, mock_pca9685, six_servo_configs):
        """Sjekk at validate_angles avviser feil antall vinkler.

        Det ma alltid vaere noyaktig 6 vinkler.
        """
        array = ServoArray(six_servo_configs, mock_pca9685)
        assert array.validate_angles([90.0] * 4) is False
