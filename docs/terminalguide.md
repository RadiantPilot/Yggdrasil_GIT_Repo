# Terminalguide

Hvordan sette opp og kjøre prosjektet pa Raspberry Pi-en.


## Forstegangsoppsett

Gjøres en gang per Pi.


### 1. SSH fra VS Code til Pi-en

Installer "Remote - SSH" i VS Code, trykk F1 og velg `Remote-SSH: Connect to Host...`.

```
ssh sivert@172.20.10.3
```


### 2. Klon repoet

```bash
git clone <repo-url> Yggdrasil_GIT_Repo
cd Yggdrasil_GIT_Repo
```


### 3. Skru pa I2C

```bash
sudo raspi-config
```

`Interface Options` -> `I2C` -> `Enable`. Restart Pi-en.


### 4. Lag venv

```bash
python3 -m venv .venv
source .venv/bin/activate
```

`(.venv)` skal vises foran prompten.
Dette er et virituelt miljø og trengs for å laste ned pakker til prosjektet.

### 5. Installer pakker

```bash
pip install -e ".[gui,hardware]"
```

Pakkegrupper:

- `gui` - PySide6, pyqtgraph
- `hardware` - smbus2
- `dev` - pytest

Kan ta noen få minutter første gang. `-e` gjor at kodeendringer trer i kraft uten ny install.



## Daglig bruk


### Aktiver venv (virituelt miljø)

```bash
source .venv/bin/activate
```


### Hent siste endringer fra github repoet

```bash
git pull
```


### Skru pa PWM-utgangene (GPIO 18 lav)

PCA9685 sin OE-pinne er koblet til GPIO 18. Den må settes lav for at servoene skal motta signal:

Sjekker status på pin 18
```bash
pinctrl get 18
```
Sett pin 18 output lav (det du må gjøre i oppsett fasen)
```bash
pinctrl set 18 op dl
```
Sett pin 18 output høy
```bash
pinctrl set 18 op dh
```
Sett pin 18 som input med pull up
```bash
pinctrl set 18 ip pu
```

Når GPIO 18 er satt til å være høy kuttes alle PWM-signaler. Har planer om å bruke aktivt i prosjektet, men det er ikke integret per dags dato (03.05). 


### Kjør tester

```bash
python -m pytest tests/ -v
```

Sjekker om det har oppstått noen følgefeil som resultat av endringer av koden. 


### GUI med mock

```bash
python -m stewart_platform.gui --mock
```

Viser hvordan GUI ser ut, uten at hardware er satt opp eller tilkoblet. Dette er altså bare en simulering.


### Full kjøring

```bash
python -m stewart_platform.gui
```

Husk å koble til labbspenning. Hvis du ikke gjør det kommer du til å få mye feilmeldinger.


### Uten GUI

`test_run.py` i prosjektrota:

```python
from stewart_platform.config import PlatformConfig
from stewart_platform.control import MotionController

config = PlatformConfig.load("config/default_config.yaml")
controller = MotionController(config)

controller.initialize()
controller.step()
print(controller.get_servo_angles())
controller.shutdown()
```

```bash
python test_run.py
```



## Mulige feil
Nesten alle feilene (hvor koden ikke kjører) har kommet av at labbspenning er skrudd av, så sjekk dette før annen eventuell feilsøking

### I2C henger seg opp

```bash
sudo i2cdetect -y 1
```

Skal vise `40` (PCA9685) og `6a` (IMU). Bare `--` betyr som regel feil med GND, VCC eller pull-up. `--` kan også komme av at labbspenningen ikke er koblet til.
