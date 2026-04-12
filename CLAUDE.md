# Stewart Platform - Prosjektretningslinjer

## Prosjektbeskrivelse
6-DOF Stewart-plattform styrt av Raspberry Pi 4B med 6 servomotorer.
Plattformen er under utvikling og krever mye tuning og fleksibilitet.

## Arkitektur
Objektorientert Python-design med 7 pakker:

```
stewart_platform/
  config/          -> PlatformConfig, ServoConfig, PIDGains, SafetyConfig
  hardware/        -> I2CBus, PCA9685Driver, IMUInterface, LSM6DSOXDriver
  geometry/        -> Vector3, Pose, PlatformGeometry
  servo/           -> Servo, ServoArray
  kinematics/      -> InverseKinematics
  control/         -> PIDController, PoseController, IMUFusion, MotionController
  safety/          -> SafetyMonitor, SafetyCheckResult, SafetySeverity
```

UML-diagram: `docs/stewart_platform.puml`
Standard konfigurasjon: `config/default_config.yaml`

## Maskinvare
- **Kontroller:** Raspberry Pi 4B
- **Servomotorer:** 6 stk, styrt via PCA9685 PWM-driver (I2C, standard 0x40)
- **IMU bunnplate:** LSM6DSOXTR (I2C, standard 0x6A)
- Alle I2C-adresser er konfigurerbare i `config/default_config.yaml`

## Designprinsipper
- **Alle parametere i config-pakken.** Ingenting hardkodet i logikk-kode.
- **YAML-drevet konfigurasjon.** Endre oppforsel uten kodeendringer.
- **Hver servo individuelt konfigurerbar:** kanal, pulsbredde, vinkelgrenser, retning, offset, monteringsvinkel.
- **Abstrakt IMU-interface.** Lett a bytte IMU-type.
- **Sikkerhet forst.** SafetyMonitor validerer alt for servoer beveger seg.

## GUI (planlagt)
Det skal lages en GUI som:
- Viser sanntidsdata fra bunnplate-IMU (akselerasjon, gyroskop, orientering)
- Viser navaerende og mal-pose (translasjon + rotasjon)
- Viser servovinkler for alle 6 servoer
- Lar brukeren endre mal-pose interaktivt (sliders/input for X, Y, Z, roll, pitch, yaw)
- Lar brukeren justere PID-parametere i sanntid
- Lar brukeren endre plattformkonfigurasjon (geometri, servo-innstillinger, I2C-adresser)
- Viser sikkerhetsstatus og kan utlose/tilbakestille nodstopp
- Viser arbeidsomrade-visualisering

For a stotte dette ma implementasjonen eksponere:
- Getters for all intern tilstand (poser, vinkler, IMU-data, PID-tilstand)
- Setters for mal-pose og konfigurasjon som validerer input
- Callback/observer-pattern eller polling-interface for sanntidsdata
- Tydelig separasjon mellom kontrolllogikk og presentasjon

## Kodesprak og stil
- Python 3.9+
- Dokumentasjon og kommentarer pa norsk
- Type hints pa alle funksjoner
- Dataclasses for konfigurasjon
- ABC for abstrakte interfaces
- numpy for matematikk

## Testing
- Tester i `tests/` med pytest
- Testfiler speiler pakkestruktur: `tests/test_<pakke>_<modul>.py`
- Tester definerer forventet oppforsel for implementasjonen
- Hardware-avhengige klasser testes med mocks

## Kommandoer
- Kjor tester: `python -m pytest tests/ -v`
- Kjor enkelt test: `python -m pytest tests/test_geometry_vector3.py -v`
