# Terminalguide

Hvordan sette opp og kjore prosjektet pa Raspberry Pi-en.


## Forstegangsoppsett

Gjores en gang per Pi.


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


### 5. Installer pakker

```bash
pip install -e ".[gui,hardware]"
```

Pakkegrupper:

- `gui` - PySide6, pyqtgraph
- `hardware` - smbus2
- `dev` - pytest

Tar 5-15 min forste gang. `-e` gjor at kodeendringer trer i kraft uten ny install.



## Daglig bruk


### Aktiver venv

```bash
source .venv/bin/activate
```


### Hent siste endringer

```bash
git pull
```


### Skru pa PWM-utgangene (GPIO 18 lav)

PCA9685 sin OE-pinne er koblet til GPIO 18. Den ma settes lav for at servoene skal motta signal:

```bash
gpioset gpiochip0 18=0
```

OE er aktiv lav. Settes GPIO 18 hoy igjen kuttes alle PWM-signaler - praktisk som rask nodstopp.


### Kjor tester

```bash
python -m pytest tests/ -v
```

Mocker maskinvaren, trenger ingen tilkoblinger.


### GUI med mock

```bash
python -m stewart_platform.gui --mock
```

Simulerer all hardware. Nyttig pa PC eller for hardware er klar.


### Full kjoring

```bash
python -m stewart_platform.gui
```

Forste gang: kjor uten servostrom, slik at I2C-init kan feile trygt.


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


### I2C henger seg opp

```bash
sudo i2cdetect -y 1
```

Skal vise `40` (PCA9685) og `6a` (IMU). Bare `--` betyr som regel feil med GND, VCC eller pull-up.
