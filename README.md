# Yggdrasil - Stewart Platform
6-DOF Stewart-plattform styrt av Raspberry Pi 4B med 6 servomotorer, en IMU-sensor og YAML-basert konfigurasjon. For å gjøre prosjektet mer gjennomførbart ble plattformens DOF redusert til 3 (roll, pitch og yaw). 

## To do list
- [ ] Servoenes bevegelsesretning
- [ ] Servoenes plassering
- [x] separat UML for front og back end
- [ ] Finn ut av FAT tabell (hva det er, og om vi trenger det)
- [ ] Lag enkelt deployment diagram.
- [ ] 3D design og print topp platen
- [ ] 3D design og print armene (inkludert mellomledds bolten)


## Oversikt

Yggdrasil er et kontrollsystem for en Stewart-plattform (hexapod) med 3 frihetsgrader (roll, pitch og yaw). Systemet leser orientering fra IMU-sensorer, beregner invers kinematikk og styrer 6 servomotorer via en PCA9685 PWM-driver, alt over I2C.

Plattformen er under aktiv utvikling og designet for enkel tuning og eksperimentering.

## Maskinvare

| Komponent | Type | Interface | Standard adresse |
|-----------|------|-----------|------------------|
| Kontroller | Raspberry Pi 4B | - | - |
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
  gui/             Grafisk brukergrensesnitt (PySide6 + pyqtgraph)
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

Pakken definerer avhengigheter i `pyproject.toml` og bruker valgfrie grupper
sa du kan installere kun det du trenger for ditt bruksomrade:

| Gruppe | Pakker | Nar trenger jeg det? |
|--------|--------|----------------------|
| (kjerne) | `numpy`, `PyYAML` | Alltid, installeres automatisk |
| `gui` | `PySide6`, `pyqtgraph` | For a kjore GUI-et |
| `hardware` | `smbus2` | For a snakke med I2C-enheter pa Raspberry Pi |
| `dev` | `pytest` | For a kjore tester |
| `all` | alle over | Installer alt pa en gang |

### Oppsett

```bash
# Klon repoet
git clone <repo-url>
cd Yggdrasil_GIT_Repo

# Velg det som passer for deg:

# Utvikling pa PC (GUI + tester, uten hardware)
pip install -e ".[gui,dev]"

# Full installasjon pa Raspberry Pi (hardware + GUI)
pip install -e ".[gui,hardware]"

# Alt (hardware + GUI + tester)
pip install -e ".[all]"

# Kun kjerne (bibliotekbruk uten GUI eller hardware)
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

Plattformen har et grafisk brukergrensesnitt bygget med PySide6 (Qt6) og pyqtgraph.

### Start GUI

```bash
# Kobler til ekte maskinvare (standard)
python -m stewart_platform.gui

# Simulert modus uten maskinvare, for utvikling og testing pa PC
python -m stewart_platform.gui --mock

# Alternativ konfigurasjonsfil
python -m stewart_platform.gui --config config/min_config.yaml

# Polling-rate for GUI-oppdatering (default 30 Hz)
python -m stewart_platform.gui --rate 60

# Lyst eller morkt tema
python -m stewart_platform.gui --theme dark
```

### Funksjoner

GUI-et er organisert i 6 faner:

- **Oversikt**: Sanntidsstatus for pose, servovinkler, IMU-data og sikkerhet samlet pa en skjerm
- **Pose**: Sliders for mal-pose (X, Y, Z, roll, pitch, yaw) med live tilbakemelding
- **PID**: PID-tuning i sanntid med responsplot per frihetsgrad
- **IMU**: Detaljert IMU-visning med sammenligning av faktisk vs. estimert orientering
- **Konfig**: Last og lagre YAML-konfigurasjon, juster parametere i kjoring
- **Sikkerhet**: Sikkerhetsstatus, nodstopp-knapp og hendelseslogg

Global toolbar pa toppen har Start, Stopp, Home og E-STOP tilgjengelig fra alle faner.

### Egen GUI-oppstart (programmatisk)

`python -m stewart_platform.gui` er normal inngangsport. Hvis du vil starte GUI-et
fra egen kode (for eksempel for a integrere det i en storre applikasjon), speiler
eksempelet under det som skjer internt i [stewart_platform/gui/app.py](stewart_platform/gui/app.py):

```python
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QApplication

from stewart_platform.gui.bridge.controller_bridge import ControllerBridge
from stewart_platform.gui.bridge.polling_worker import PollingWorker
from stewart_platform.gui.main_window import MainWindow

app = QApplication(sys.argv)

# mock=True for simulert modus, mock=False for ekte hardware
bridge = ControllerBridge(config_path=Path("config/default_config.yaml"), mock=False)
bridge.initialize()

worker_thread = QThread()
worker = PollingWorker(bridge, rate_hz=30.0)
worker.moveToThread(worker_thread)
worker_thread.started.connect(worker.run)

window = MainWindow(bridge)
worker.snapshot_ready.connect(window.on_snapshot, Qt.QueuedConnection)
window.show()
worker_thread.start()

sys.exit(app.exec())
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
    GUI_INFO.md                  Detaljert GUI-implementasjonsplan
    kinematikk.md                Notater om invers kinematikk
    terminalguide.md             Terminal-kommandoer og tips
    backend.puml                 UML - backend
    frontend.puml                UML - frontend
    stewart_platform_V1.puml     UML (tidlig versjon)
    stewart_platform_V2.puml     UML (mellomversjon)
    stewart_platform_V3.puml     UML-klassediagram (nyeste)
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
      app.py                     QApplication-oppsett, argparse, main()
      main_window.py             QMainWindow med QTabWidget (6 faner)
      bridge/
        controller_bridge.py     Tradsikker bro mellom GUI og MotionController
        polling_worker.py        QThread-worker som henter snapshots
        state_snapshot.py        Dataclass med samlet GUI-tilstand
      tabs/
        base_tab.py              Felles basis for alle faner
        overview_tab.py          Oversikt: pose, servo, IMU, sikkerhet
        pose_control_tab.py      Mal-pose-sliders (6-DOF)
        pid_tuning_tab.py        PID-tuning med responsplot
        imu_tab.py               IMU-data og fusjonsvisning
        config_tab.py            Last/lagre YAML, juster parametere
        safety_tab.py            Sikkerhetsstatus og hendelseslogg
      widgets/
        indicator_lamp.py        Statuslampe (gron/gul/rod)
        status_banner.py         Statusbanner pa topp av faner
        servo_bars.py            Vinkelbarer for 6 servoer
        pose_sliders.py          Sliders for 6-DOF pose
        pid_card.py              PID-tuning-kort (kp, ki, kd)
        realtime_plot.py         pyqtgraph sanntidsplot
        response_plot.py         PID-responsplot
        event_log.py             Rullende hendelseslogg
      utils/
        theme.py                 Lyst og morkt Qt-tema
        ring_buffer.py           Ringbuffer for plotdata
        formatting.py            Tallformatering for visning
  tests/
    ...                          Pytest-tester (speiler pakkestruktur)
```

## UML-diagram

Se `docs/stewart_platform_V3.puml` for nyeste klassediagram. Apne med PlantUML-utvidelsen i VS Code eller pa [plantuml.com](https://www.plantuml.com/plantuml/uml/).

Tidligere revisjoner (`stewart_platform_V1.puml`, `stewart_platform_V2.puml`) ligger ogsa i `docs/` for historikk og sammenligning.
