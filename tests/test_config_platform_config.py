# test_config_platform_config.py
# ==============================
# Tester for config-pakken: PlatformConfig, ServoConfig, PIDGains, SafetyConfig.
#
# Disse testene definerer forventet oppforsel for konfigurasjonssystemet.
# Konfigurasjonen er fundamentet for hele plattformen — alt fra geometri
# til servo-innstillinger og sikkerhetsgrenser styres herfra.
#
# GUI-relevans:
#   GUI-en skal kunne lese og endre alle konfigurasjonsparametere i sanntid.
#   Testene verifiserer at dataklassene er korrekt opprettet, at YAML
#   lasting/lagring fungerer, og at validering fanger opp ugyldige verdier.

import os
import tempfile

import pytest

from stewart_platform.config.platform_config import (
    PlatformConfig,
    ServoConfig,
    PIDGains,
    SafetyConfig,
)


# ===========================================================================
# ServoConfig — Konfigurasjon for en enkelt servo
# ===========================================================================

class TestServoConfig:
    """Tester for ServoConfig dataklasse.

    Hver servo skal ha individuelt konfigurerbare parametere for
    kanal, pulsbredde, vinkelgrenser, retning, offset og monteringsvinkel.
    GUI-en skal kunne vise og endre disse per servo.
    """

    # --- Standardverdier skal vaere fornuftige for en typisk servo ---

    def test_standardverdier_er_satt(self):
        """Sjekk at en ServoConfig med standardverdier har fornuftige defaults.

        Standardverdiene skal fungere for en typisk hobbyservo (500-2500 us,
        0-180 grader) slik at man kan komme raskt i gang.
        """
        config = ServoConfig()
        assert config.channel == 0
        assert config.min_pulse_us == 500
        assert config.max_pulse_us == 2500
        assert config.min_angle_deg == 0.0
        assert config.max_angle_deg == 180.0
        assert config.home_angle_deg == 90.0
        assert config.direction == 1
        assert config.offset_deg == 0.0
        assert config.mounting_angle_deg == 0.0

    # --- Alle parametere skal kunne settes individuelt ---

    def test_egendefinert_konfigurasjon(self):
        """Sjekk at alle parametere kan overstyres ved opprettelse.

        Viktig for tuning: hver servo kan ha unike grenser, retning
        og monteringsvinkel basert pa fysisk plassering.
        """
        config = ServoConfig(
            channel=3,
            min_pulse_us=600,
            max_pulse_us=2400,
            min_angle_deg=10.0,
            max_angle_deg=170.0,
            home_angle_deg=85.0,
            direction=-1,
            offset_deg=2.5,
            mounting_angle_deg=180.0,
        )
        assert config.channel == 3
        assert config.min_pulse_us == 600
        assert config.max_pulse_us == 2400
        assert config.min_angle_deg == 10.0
        assert config.max_angle_deg == 170.0
        assert config.home_angle_deg == 85.0
        assert config.direction == -1
        assert config.offset_deg == 2.5
        assert config.mounting_angle_deg == 180.0

    # --- Retning styrer rotasjonsretningen (+1 eller -1) ---

    def test_retning_normal(self):
        """Sjekk at direction=1 representerer normal rotasjonsretning."""
        config = ServoConfig(direction=1)
        assert config.direction == 1

    def test_retning_invertert(self):
        """Sjekk at direction=-1 representerer invertert rotasjonsretning.

        Noen servoer er montert speilvendt og trenger invertert signal.
        """
        config = ServoConfig(direction=-1)
        assert config.direction == -1


# ===========================================================================
# PIDGains — PID-regulatorforsterkning
# ===========================================================================

class TestPIDGains:
    """Tester for PIDGains dataklasse.

    PID-parametere er kritiske for tuning. GUI-en skal la brukeren
    justere kp, ki, kd i sanntid og se effekten umiddelbart.
    """

    def test_standardverdier(self):
        """Sjekk at standardverdier gir en ren P-regulator.

        ki=0 og kd=0 som standard betyr at man starter med bare
        proporsjonal kontroll, som er det sikreste utgangspunktet.
        """
        gains = PIDGains()
        assert gains.kp == 1.0
        assert gains.ki == 0.0
        assert gains.kd == 0.0
        # Standardgrensene er per-tick korreksjon i mm/grader, valgt
        # romslig nok til at en typisk feil ikke saturerer mens den
        # fortsatt er trygt under sikkerhetsenvelopen.
        assert gains.output_min == -10.0
        assert gains.output_max == 10.0
        assert gains.integral_limit == 100.0

    def test_egendefinerte_gains(self):
        """Sjekk at alle PID-parametere kan overstyres.

        Under tuning vil brukeren justere disse verdiene iterativt
        for a finne optimal respons.
        """
        gains = PIDGains(kp=2.5, ki=0.1, kd=0.05, output_min=-10.0, output_max=10.0, integral_limit=50.0)
        assert gains.kp == 2.5
        assert gains.ki == 0.1
        assert gains.kd == 0.05
        assert gains.output_min == -10.0
        assert gains.output_max == 10.0
        assert gains.integral_limit == 50.0


# ===========================================================================
# SafetyConfig — Sikkerhetsgrenser
# ===========================================================================

class TestSafetyConfig:
    """Tester for SafetyConfig dataklasse.

    Sikkerhetsgrensene beskytter plattformen mot skade. GUI-en skal
    vise naavaerende grenser og la brukeren justere dem (forsiktig).
    """

    def test_standardverdier(self):
        """Sjekk at standardverdier er konservative.

        Konservative standardverdier beskytter mot uhell under
        forste oppstart for plattformen er ferdig kalibrert.
        """
        config = SafetyConfig()
        assert config.max_translation_mm == 50.0
        assert config.max_rotation_deg == 30.0
        assert config.max_velocity_mm_per_s == 100.0
        assert config.max_angular_velocity_deg_per_s == 60.0
        assert config.servo_angle_margin_deg == 5.0
        assert config.watchdog_timeout_s == 1.0
        assert config.imu_fault_threshold_g == 4.0

    def test_egendefinerte_grenser(self):
        """Sjekk at sikkerhetsgrenser kan justeres.

        Etter kalibrering kan grensene utvides for a utnytte
        plattformens fulle bevegelsesomrade.
        """
        config = SafetyConfig(
            max_translation_mm=80.0,
            max_rotation_deg=45.0,
            max_velocity_mm_per_s=200.0,
            max_angular_velocity_deg_per_s=120.0,
            servo_angle_margin_deg=2.0,
            watchdog_timeout_s=0.5,
            imu_fault_threshold_g=8.0,
        )
        assert config.max_translation_mm == 80.0
        assert config.max_rotation_deg == 45.0
        assert config.max_velocity_mm_per_s == 200.0


# ===========================================================================
# PlatformConfig — Hovedkonfigurasjon
# ===========================================================================

class TestPlatformConfig:
    """Tester for PlatformConfig dataklasse.

    PlatformConfig er rotkonfigurasjonen som samler alt. GUI-en
    bruker denne for a lese/skrive hele konfigurasjonstilstanden.
    """

    # --- Standardverdier ---

    def test_standardverdier_i2c(self):
        """Sjekk at I2C-standardadresser er korrekte.

        Standardadressene skal matche typisk maskinvareoppsett:
        PCA9685=0x40, LSM6DSOX=0x6A.
        """
        config = PlatformConfig()
        assert config.i2c_bus_number == 1
        assert config.pca9685_address == 0x40
        assert config.pca9685_frequency == 50
        assert config.lsm6dsox_address == 0x6A

    def test_standardverdier_geometri(self):
        """Sjekk at geometristandardverdier er satt.

        Geometrien beskriver fysiske dimensjoner i mm og grader.
        """
        config = PlatformConfig()
        assert config.base_radius == 100.0
        assert config.platform_radius == 75.0
        assert config.servo_horn_length == 25.0
        assert config.rod_length == 150.0
        assert config.home_height == 120.0
        assert len(config.base_joint_angles) == 6
        assert len(config.platform_joint_angles) == 6

    def test_seks_servoer_som_standard(self):
        """Sjekk at det opprettes noyaktig 6 servokonfigurasjoner.

        En Stewart-plattform har alltid 6 aktuatorer.
        """
        config = PlatformConfig()
        assert len(config.servo_configs) == 6

    def test_servo_kanaler_er_unike(self):
        """Sjekk at standard servokonfigurasjoner har unike kanaler.

        Hver servo ma ha sin egen PCA9685-kanal for a unnga konflikter.
        """
        config = PlatformConfig()
        channels = [s.channel for s in config.servo_configs]
        assert len(set(channels)) == 6

    def test_underkonfigurasjoner_er_instanser(self):
        """Sjekk at PID og safety er riktige dataklasse-instanser.

        PlatformConfig skal eie sine underkonfigurasjoner.
        """
        config = PlatformConfig()
        assert isinstance(config.pid_gains, PIDGains)
        assert isinstance(config.safety_config, SafetyConfig)

    # --- Leddvinkler ---

    def test_leddvinkler_bunnplate(self):
        """Sjekk at bunnplatens leddvinkler er jevnt fordelt.

        Standard: 6 ledd jevnt fordelt med 60 graders mellomrom.
        """
        config = PlatformConfig()
        assert config.base_joint_angles == [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]

    def test_leddvinkler_toppplate(self):
        """Sjekk at toppplatens leddvinkler er forskjovne 30 grader.

        Toppplaten er rotert 30 grader relativt til bunnplaten
        for a gi kryssende bein som oker stabiliteten.
        """
        config = PlatformConfig()
        assert config.platform_joint_angles == [30.0, 90.0, 150.0, 210.0, 270.0, 330.0]

    # --- YAML lasting og lagring ---

    def test_yaml_load_eksisterer(self):
        """Sjekk at load-metoden finnes som klassemetode.

        GUI-en bruker load() for a laste en konfigurasjonsfil ved oppstart.
        """
        assert hasattr(PlatformConfig, 'load')
        assert callable(getattr(PlatformConfig, 'load'))

    def test_yaml_save_eksisterer(self):
        """Sjekk at save-metoden finnes.

        GUI-en bruker save() for a lagre endringer brukeren gjor.
        """
        config = PlatformConfig()
        assert hasattr(config, 'save')
        assert callable(getattr(config, 'save'))

    def test_yaml_roundtrip(self, tmp_path):
        """Sjekk at en konfigurasjon kan lagres til YAML og lastes tilbake identisk.

        Roundtrip-test: lagre -> last -> sammenlign. Verdiene skal vaere
        identiske for og etter serialisering.
        """
        original = PlatformConfig(
            base_radius=120.0,
            platform_radius=80.0,
            home_height=130.0,
            pca9685_address=0x41,
        )
        filepath = str(tmp_path / "test_config.yaml")
        original.save(filepath)
        loaded = PlatformConfig.load(filepath)

        assert loaded.base_radius == original.base_radius
        assert loaded.platform_radius == original.platform_radius
        assert loaded.home_height == original.home_height
        assert loaded.pca9685_address == original.pca9685_address

    def test_yaml_load_med_servokonfigurasjon(self, tmp_path):
        """Sjekk at servokonfigurasjoner overlever YAML-roundtrip.

        Viktig at individuelle servo-innstillinger (retning, offset)
        bevares korrekt gjennom serialisering.
        """
        original = PlatformConfig()
        original.servo_configs[0].direction = -1
        original.servo_configs[0].offset_deg = 3.5
        original.servo_configs[2].mounting_angle_deg = 125.0

        filepath = str(tmp_path / "test_servo_config.yaml")
        original.save(filepath)
        loaded = PlatformConfig.load(filepath)

        assert loaded.servo_configs[0].direction == -1
        assert loaded.servo_configs[0].offset_deg == 3.5
        assert loaded.servo_configs[2].mounting_angle_deg == 125.0

    def test_yaml_load_med_pid_gains(self, tmp_path):
        """Sjekk at PID-gains overlever YAML-roundtrip.

        GUI-en lagrer justerte PID-verdier — de ma vaere identiske
        etter lasting.
        """
        original = PlatformConfig()
        original.pid_gains = PIDGains(kp=3.0, ki=0.5, kd=0.1)

        filepath = str(tmp_path / "test_pid_config.yaml")
        original.save(filepath)
        loaded = PlatformConfig.load(filepath)

        assert loaded.pid_gains.kp == 3.0
        assert loaded.pid_gains.ki == 0.5
        assert loaded.pid_gains.kd == 0.1

    def test_load_fra_default_config_yaml(self):
        """Sjekk at standardkonfigurasjonsfilen kan lastes.

        config/default_config.yaml skal alltid vaere en gyldig fil
        som kan lastes uten feil.
        """
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config",
            "default_config.yaml",
        )
        if not os.path.exists(config_path):
            pytest.skip("default_config.yaml ikke funnet")

        config = PlatformConfig.load(config_path)
        assert isinstance(config, PlatformConfig)
        assert len(config.servo_configs) == 6
        assert config.pca9685_address == 0x40

    # --- Validering ---

    def test_validate_eksisterer(self):
        """Sjekk at validate-metoden finnes.

        Validering er viktig for GUI-en: brukeren kan skrive inn
        vilkarlige verdier, og validate() skal fange feil.
        """
        config = PlatformConfig()
        assert hasattr(config, 'validate')
        assert callable(getattr(config, 'validate'))

    def test_validate_godtar_standard(self):
        """Sjekk at standardkonfigurasjonen passerer validering.

        Standardverdiene skal alltid vaere gyldige.
        """
        config = PlatformConfig()
        errors = config.validate()
        assert errors == []

    def test_validate_returnerer_liste(self):
        """Sjekk at validate returnerer en liste med feilmeldinger."""
        config = PlatformConfig()
        result = config.validate()
        assert isinstance(result, list)

    def test_validate_feiler_for_feil_antall_servoer(self):
        """Sjekk at validering feiler hvis det ikke er noyaktig 6 servoer.

        En Stewart-plattform krever noyaktig 6 aktuatorer.
        """
        config = PlatformConfig()
        config.servo_configs = [ServoConfig(channel=i) for i in range(4)]
        errors = config.validate()
        assert len(errors) > 0
        assert "6 servokonfigurasjoner" in errors[0]

    def test_validate_feiler_for_negative_dimensjoner(self):
        """Sjekk at validering feiler for negative geometriverdier.

        Radius, staglengde og hoyde ma vaere positive tall.
        """
        config = PlatformConfig(base_radius=-10.0)
        errors = config.validate()
        assert len(errors) > 0
        assert "base_radius" in errors[0]

    def test_validate_feiler_for_ugyldig_vinkelomrade(self):
        """Sjekk at validering feiler hvis min_angle >= max_angle for en servo.

        Vinkelomradet ma vaere gyldig: minimum skal vaere mindre enn maksimum.
        """
        config = PlatformConfig()
        config.servo_configs[0].min_angle_deg = 180.0
        config.servo_configs[0].max_angle_deg = 0.0
        errors = config.validate()
        assert len(errors) > 0

    def test_validate_samler_flere_feil(self):
        """Sjekk at validate returnerer alle feil, ikke bare den forste."""
        config = PlatformConfig(base_radius=-10.0, platform_radius=-5.0)
        errors = config.validate()
        assert len(errors) >= 2

    def test_raise_if_invalid_ok(self):
        """Sjekk at raise_if_invalid ikke kaster for gyldig config."""
        config = PlatformConfig()
        config.raise_if_invalid()  # Skal ikke kaste

    def test_raise_if_invalid_kaster_valueerror(self):
        """Sjekk at raise_if_invalid kaster ValueError for ugyldig config."""
        config = PlatformConfig(base_radius=-10.0)
        with pytest.raises(ValueError):
            config.raise_if_invalid()

    # --- GUI-relevant: I2C-adresser lett justerbare ---

    def test_i2c_adresser_kan_endres(self):
        """Sjekk at I2C-adresser kan settes til egendefinerte verdier.

        GUI-en skal ha felt for a endre I2C-adresser nar brukeren
        har endret adressepinnene pa komponentene.
        """
        config = PlatformConfig(
            pca9685_address=0x41,
            lsm6dsox_address=0x6B,
        )
        assert config.pca9685_address == 0x41
        assert config.lsm6dsox_address == 0x6B
