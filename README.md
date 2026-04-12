# Yggdrasil - Stewart Platform

6-DOF Stewart-plattform styrt av Raspberry Pi 4B med 6 servomotorer, en IMU-sensor og YAML-basert konfigurasjon.

## Oversikt

Yggdrasil er et kontrollsystem for en Stewart-plattform (hexapod) med 6 frihetsgrader. Systemet leser orientering fra IMU-sensorer, beregner invers kinematikk og styrer 6 servomotorer via en PCA9685 PWM-driver — alt over I2C.

Plattformen er under aktiv utvikling og designet for enkel tuning og eksperimentering.

## Maskinvare

| Komponent | Type | Interface | Standard adresse |
|-----------|------|-----------|------------------|
| Kontroller | Raspberry Pi 4B | — | — |
| PWM-driver | PCA9685 (16-kanals) | I2C | 0x40 |
| IMU bunnplate | LSM6DSOXTR | I2C | 0x6A |
| Servomotorer | 6 stk | PWM via PCA9685 | Kanal 0-5 |

Alle I2C-adresser kan endres i `config/default_config.yaml`.

## Arkitektur

Objektorientert Python-design med 8 pakker:

```
stewart_platform/
  config/          Konfigurasjon og justerbare parametere
  hardware/        I2C-buss, PWM-driver, IMU-drivere
  geometry/        3D-vektorer, 6-DOF poser, plattformgeometri
  servo/           Individuell og batch servostyring
  kinematics/      Invers kinematikk (pose -> servovinkler)
  control/         PID-regulering, sensorfusjon, kontrollslyfe
  safety/          Sikkerhetsvalidering og nodstopp
  gui/             Grafisk brukergrensesnitt (CustomTkinter + matplotlib)
```

### Kontrollslyfe

```
IMU-data -> IMUFusion -> PoseController (PID) -> InverseKinematics -> SafetyMonitor -> ServoArray
```

1. Les akselerometer og gyroskop fra bunnplate-IMU
2. Estimer orientering via komplementaerfilter (IMUFusion)
3. Beregn korreksjon med PID-regulator (PoseController)
4. Los invers kinematikk for 6 servovinkler (InverseKinematics)
5. Valider mot sikkerhetsgrenser (SafetyMonitor)
6. Send servovinkler til PCA9685 (ServoArray)

## Installasjon

### Krav

- Python 3.9+
- Raspberry Pi 4B (for maskinvarestyring)
- Tilkoblede I2C-enheter (PCA9685, LSM6DSOXTR)

### Avhengigheter

| Pakke | Bruk |
|-------|------|
| `numpy` | Matematikk og lineaer algebra |
| `pyyaml` | YAML-konfigurasjonsfiler |
| `smbus2` | I2C-kommunikasjon (Raspberry Pi) |
| `customtkinter` | Moderne GUI (mork tema, avrundede widgets) |
| `matplotlib` | 3D-visualisering av plattformen |

### Oppsett

```bash
# Klon repoet
git clone <repo-url>
cd Yggdrasil_GIT_Repo

# Installer avhengigheter
pip install numpy pyyaml smbus2 customtkinter matplotlib

# Installer som utviklingspakke (valgfritt)
pip install -e .
```

### Aktiver I2C pa Raspberry Pi

```bash
sudo raspi-config
# Interface Options -> I2C -> Enable

# Verifiser at enheter er synlige
i2cdetect -y 1
```

## Konfigurasjon

All konfigurasjon styres via YAML-filer. Rediger `config/default_config.yaml` for a tilpasse systemet uten kodeendringer.

### Eksempel: Last og bruk konfigurasjon

```python
from stewart_platform.config import PlatformConfig

# Last konfigurasjon fra fil
config = PlatformConfig.load("config/default_config.yaml")

# Valider at konfigurasjonen er konsistent
config.validate()

# Endre og lagre
config.pid_gains.kp = 2.0
config.save("config/my_config.yaml")
```

### Justerbare parametere

**I2C-adresser:**
```yaml
pca9685_address: 0x40
lsm6dsox_address: 0x6A
```

**Plattformgeometri** (mm og grader):
```yaml
base_radius: 100.0
platform_radius: 75.0
servo_horn_length: 25.0
rod_length: 150.0
home_height: 120.0
base_joint_angles: [0, 60, 120, 180, 240, 300]
platform_joint_angles: [30, 90, 150, 210, 270, 330]
```

**Per-servo konfigurasjon:**
```yaml
servo_configs:
  - channel: 0              # PCA9685-kanal
    min_pulse_us: 500        # Min pulsbredde (us)
    max_pulse_us: 2500       # Maks pulsbredde (us)
    min_angle_deg: 0.0       # Mekanisk minstevinkel
    max_angle_deg: 180.0     # Mekanisk maksimumsvinkel
    home_angle_deg: 90.0     # Noytralposisjon
    direction: 1             # +1 normal, -1 invertert
    offset_deg: 0.0          # Kalibreringsoffset
    mounting_angle_deg: 0.0  # Monteringsvinkel pa bunnplate
```

**PID-regulering:**
```yaml
pid_gains:
  kp: 1.0
  ki: 0.0
  kd: 0.0
```

## Bruk

### Grunnleggende oppstart

```python
from stewart_platform.config import PlatformConfig
from stewart_platform.control import MotionController
from stewart_platform.geometry import Pose, Vector3

# Last konfigurasjon og opprett kontroller
config = PlatformConfig.load("config/default_config.yaml")
controller = MotionController(config)

# Initialiser maskinvare (I2C, servoer, IMU)
controller.initialize()

# Sett en mal-pose: 10 mm opp og 5 grader pitch
target = Pose(
    translation=Vector3(0.0, 0.0, 10.0),
    rotation=Vector3(0.0, 5.0, 0.0),
)
controller.set_target_pose(target)

# Start kontrollslyfen
controller.start()
```

### Manuell stegvis kontroll

```python
# Kjor en enkelt iterasjon (nyttig for testing)
controller.step()

# Les navaerende tilstand
print(controller.get_current_pose())
print(controller.get_servo_angles())
```

### Nodstopp

```python
# Frikobler alle servoer umiddelbart
controller.emergency_stop()

# Sikker avslutning
controller.shutdown()
```

## GUI

Plattformen har et grafisk brukergrensesnitt bygget med CustomTkinter og matplotlib.

### Start GUI

```bash
# Demo-modus (uten maskinvare — for utvikling og testing pa PC)
python -m stewart_platform.gui
```

### Funksjoner

- **Tilt-styring**: Interaktiv sirkel for roll/pitch-kontroll. To modi:
  - *Live*: Klikk og dra for a styre plattformen i sanntid
  - *Visning*: Skrivebeskyttet kryss som viser faktisk orientering
- **3D-visning**: Live matplotlib-modell av plattformen (bunnplate, toppplate, 6 bein)
- **IMU-panel**: Sammenligning av faktisk (ekstern IMU) og estimert (RPi-fusjon) orientering
- **Sikkerhetsbar**: Permanent NODSTOPP-knapp og sikkerhetsstatus nederst i vinduet
- **Servokontroll**: Popup for direkte servostyring (testing/kalibrering)
- **Innstillinger**: Popup med PID-tuning, sikkerhetsgrenser, og konfigurasjon (YAML lagre/last)

### Koble til maskinvare

```python
from stewart_platform.config import PlatformConfig
from stewart_platform.control import MotionController
from stewart_platform.geometry.platform_geometry import PlatformGeometry
from stewart_platform.gui.app import StewartPlatformApp

config = PlatformConfig.load("config/default_config.yaml")
controller = MotionController(config)
controller.initialize()
geometry = PlatformGeometry(config)

app = StewartPlatformApp(config=config, controller=controller, geometry=geometry)
app.mainloop()
```

## Testing

```bash
# Kjor alle tester
python -m pytest tests/ -v

# Kjor tester for en spesifikk pakke
python -m pytest tests/test_geometry_vector3.py -v
```

Tester bruker mocks for maskinvareavhengige klasser (I2C, PCA9685, IMU).

## Filstruktur

```
Yggdrasil_GIT_Repo/
  config/
    default_config.yaml          Standard konfigurasjon (YAML)
  docs/
    stewart_platform.puml        UML-klassediagram (PlantUML)
  stewart_platform/
    __init__.py
    config/
      platform_config.py         PlatformConfig, ServoConfig, PIDGains, SafetyConfig
    hardware/
      i2c_bus.py                 I2CBus - wrapper rundt smbus2
      pca9685_driver.py          PCA9685Driver - 16-kanals PWM
      imu_interface.py           IMUInterface - abstrakt IMU-grensesnitt
      lsm6dsox_driver.py         LSM6DSOXDriver - bunnplate-IMU
    geometry/
      vector3.py                 Vector3 - 3D-vektor
      pose.py                    Pose - 6-DOF posisjon + orientering
      platform_geometry.py       PlatformGeometry - leddposisjoner og beinlengder
    servo/
      servo.py                   Servo - enkelt servostyring
      servo_array.py             ServoArray - batch-styring av 6 servoer
    kinematics/
      inverse_kinematics.py      InverseKinematics - pose til servovinkler
    control/
      pid_controller.py          PIDController - PID med anti-windup
      pose_controller.py         PoseController - 6x PID (en per DOF)
      imu_fusion.py              IMUFusion - komplementaerfilter
      motion_controller.py       MotionController - hovedkontrollslyfe
    safety/
      safety_monitor.py          SafetyMonitor, SafetyCheckResult, SafetySeverity
    gui/
      __main__.py                Startpunkt: python -m stewart_platform.gui
      app.py                     Hovedvindu (CTk), faner, mainloop
      data_bridge.py             Tradsikker bro mellom GUI og kontrolltrad
      theme.py                   Farger, fonter, storrelser
      views/
        tilt_control.py          Fane 1: Interaktiv tilt-sirkel
        platform_3d.py           Fane 2: Matplotlib 3D-visning
      components/
        top_bar.py               Tilstand, start/stopp, menyknapper
        safety_bar.py            NODSTOPP og sikkerhetsstatus
        imu_panel.py             IMU-sammenligning (faktisk vs. estimert)
      popups/
        servo_menu.py            Direkte servostyring (testing)
        settings_window.py       PID, sikkerhet, konfigurasjon
      widgets/
        tilt_circle.py           Canvas-basert tilt-sirkel
        platform_renderer.py     Matplotlib 3D-tegning av plattformen
  tests/
    ...                          Pytest-tester (speiler pakkestruktur)
```

## UML-diagram

Se `docs/stewart_platform.puml` for komplett klassediagram. Apne med PlantUML-utvidelsen i VS Code eller pa [plantuml.com](https://www.plantuml.com/plantuml/uml/).
