# Yggdrasil – Stewart Platform

6-DOF Stewart-plattform styrt av Raspberry Pi 4B med 6 servomotorer og sanntids IMU-tilbakekobling.
Systemet er skrevet i Python med et PySide6-basert GUI for manuell styring, PID-tuning og sikkerhetsovervåking.

---

## Maskinvare

| Komponent | Type | Grensesnitt | Standard adresse |
|-----------|------|-------------|-----------------|
| Kontroller | Raspberry Pi 4B | – | – |
| Knappekort | ATTINY1624 (valgfri) | I2C | 0x20 |
| IMU (bunnplate) | LSM6DSOXTR | I2C | 0x6A |
| PWM-driver | PCA9685 (16-kanal) | I2C | 0x40 |
| Servoer | 6× standard | PWM via PCA9685 | Kanal 0–5 |


Alle I2C-adresser er konfigurerbare i `config/default_config.yaml`.

---

## Installasjon

```bash
git clone <repo-url>
cd Yggdrasil_GIT_Repo
python3 -m venv .venv
source .venv/bin/activate
```

Velg installasjonsprofil etter behov (du trenger alt, men det var lett å lage alternativer... :-D ):

```bash
pip install -e ".[dev]"            # PC-utvikling – kun kjerne + testing, ingen GUI eller hardware
pip install -e ".[gui,dev]"        # PC med GUI og testing
pip install -e ".[gui,hardware]"   # Raspberry Pi – full installasjon
pip install -e ".[all]"            # Alt
```

For RPi-spesifikt oppsett (I2C-aktivering, GPIO PWM, daglig bruk): se [docs/terminalguide.md](docs/terminalguide.md)

---

## Alternativer for å kjøre GUI

```bash
python -m stewart_platform.gui                              # Ekte hardware
python -m stewart_platform.gui --mock                       # Simulert – ingen hardware nødvendig
python -m stewart_platform.gui --config config/min.yaml     # Alternativ konfigurasjonsfil
python -m stewart_platform.gui --theme dark                 # Mørkt tema
python -m stewart_platform.gui --rate 60                    # Polling-frekvens for GUI (Hz)
```

GUI-et har 5 faner: Oversikt, PID-tuning, IMU, Konfigurasjon og Sikkerhet.
Full GUI-referanse (alle faner, argumenter, tastatur, knappekort): se [docs/GUI_INFO.md](docs/GUI_INFO.md)

---

## Testing

```bash
python -m pytest tests/ -v
python -m pytest tests/test_geometry_vector3.py -v
```

Tester bruker mocks for all hardware (I2C, PCA9685, IMU) og kjører uten Raspberry Pi.

---

## Konfigurasjon

Alle parametere styres fra `config/default_config.yaml` – ingen hardkodede verdier i logikken.

Viktigste seksjoner:

```yaml
# I2C-adresser
pca9685_address: 0x40
lsm6dsox_address: 0x6A

# Geometri (mm og grader)
base_radius: 100.0
platform_radius: 75.0
servo_horn_length: 25.0
rod_length: 150.0
home_height: 120.0

# Servokonfigurasjon (en per servo, kanal 0–5)
servo_configs:
  - channel: 0
    home_angle_deg: 90.0
    direction: 1           # +1 normal, -1 invertert
    offset_deg: 0.0        # Kalibreringsoffset

# PID-regulering
pid_gains:
  kp: 1.0
  ki: 0.0
  kd: 0.0

# Sikkerhetsgrenser
safety_config:
  max_rotation_deg: 30.0
  max_angular_velocity_deg_per_s: 60.0
```

Last inn en egendefinert konfigurasjon med `--config <sti>` ved oppstart.
Konfigurasjonen kan også lagres og redigeres direkte fra GUI som Konfigurasjons fane.

---

## Arkitektur

**Kontrollsløyfe (25 Hz):**

```
IMU → IMUFusion → PoseController (PID) → InverseKinematics → SafetyMonitor → ServoArray
```

**Pakkestruktur:**

| Pakke | Innhold |
|-------|---------|
| `config/` | PlatformConfig, ServoConfig, PIDGains, SafetyConfig – all konfigurasjon |
| `hardware/` | I2CBus, PCA9685Driver, LSM6DSOXDriver, knappegrensesnitt |
| `geometry/` | Vector3, Pose, PlatformGeometry – 3D-matematikk |
| `servo/` | Servo, ServoArray – PWM-kontroll |
| `kinematics/` | InverseKinematics – pose til servovinkler |
| `control/` | PIDController, IMUFusion, MotionController – regulatorlogikk |
| `safety/` | SafetyMonitor – validering og nødstopp |
| `gui/` | PySide6-app med 5 faner, bro mot kontrolleren, widgets |

For matematisk grunnlag for invers kinematikk, se: [docs/kinematikk.md](docs/kinematikk.md)  
For UML klassediagram, se: [docs/stewart_platform_V3.puml](docs/stewart_platform_V3.puml)

---

## Bringup-scripts

Scripts i `scripts/` brukes til hardware-verifisering og kalibrering:

| Script | Formål |
|--------|--------|
| `bringup_imu.py` | Verifiser IMU-kommunikasjon og leseverdier |
| `bringup_pca9685.py` | Verifiser PCA9685-driver |
| `bringup_one_servo.py` | Test og kalibrer én enkelt servo |
| `home_all_servos.py` | Flytt alle 6 servoer til hjemposisjon |
| `sweep_all_servos.py` | Test fullt bevegelsesområde for alle servoer |
| `check_home_geometry.py` | Valider hjemgeometrien mot konfigurasjonen |

---

## Annen kode

`firmware/knappekort.ino` – ATTINY1624 koden, for I2C delen av knappekort (adresse 0x20).
