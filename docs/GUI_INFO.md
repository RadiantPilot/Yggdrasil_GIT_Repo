# GUI

Dette dokumentet er en introduksjon til GUI for prosjekt Yggdrasil

## Starte GUI
Med hardware:

```bash
python -m stewart_platform.gui
```

Uten hardware (simulert):

```bash
python -m stewart_platform.gui --mock
```

Argumenter:

- `--mock` — simulerer alt av hardware (servoer, IMU, knapper)
- `--config PATH` — annen YAML-fil enn `config/default_config.yaml`
- `--rate 30` — polling-frekvens i Hz (hvor ofte GUI henter ny tilstand)
- `--theme light` eller `--theme dark` — startstema (`--theme dark` er satt som default)



## Layout

Vinduet har tre deler: topbar øverst, faner i midten, statusbar nederst.


### Topbar

| Knapp | Hva den gjør |
|---|---|
| Start | Starter kontrollsløyfen |
| Stopp | Stopper sløyfen (servoer holder posisjonen sin) |
| Home | Setter mål-pose til (0,0,0) og kjører servoer til hvilevinkel |
| Modus | Viser `SIMULERT` eller `HARDWARE` |
| Hz | Viser loop-frekvensen |
| E-STOP (F1) | Nødstopp — frikobler servoer umiddelbart |

E-STOP kan også utløses med `F1`. Reset gjøres fra Sikkerhet-fanen.


### Faner

1. **Oversikt** — generell oversikt: pose, servovinkler, IMU, hendelseslogg
2. **Pose-kontroll** — sliders for X, Y, Z, roll, pitch, yaw
3. **PID-tuning** — kp/ki/kd per akse, step-respons-plot
4. **IMU** — akselerometer, gyro, kalibreringsknapper
5. **Konfig** — geometri, servoer, I2C-adresser, lagre/laste YAML
6. **Sikkerhet** — grenser, historikk, reset av E-STOP


### Statusbar

Viser siste hendelse, f.eks. `Start-kommando sendt` eller `E-STOP aktivert`.


### Navigasjon med knappekort

Det fysiske knappekortet (eller piltastene + Enter) styrer fokus mellom fanene og widgetene. `F2` = lang-trykk midt = E-STOP via knappemodellen.



## Hva skjer egentlig

GUI-et snakker aldri direkte med servoer eller IMU. Alt går via `ControllerBridge`, som er den eneste delen av GUI som kjenner til hardware.

Tre tråder kjører samtidig:

- **Hovedtråd (Qt)** — tegner widgets, tar imot input
- **Kontrolltråd** — kjører styringssløyfen på 100 Hz, leser IMU og setter servoer
- **Polling-worker** — leser et `StateSnapshot` (pose, vinkler, IMU, sikkerhet) på 30 Hz og sender det til GUI-et

GUI-et oppdaterer kun den synlige fanen for å spare CPU.


### Mock vs hardware

`--mock` bytter ut hele hardware-laget med simulert data — sinusbevegelse på pose, gyngende servovinkler, IMU rundt 9.81 m/s². 



## Feilmeldinger

Meldinger dukker opp i hendelsesloggen (Oversikt-fanen) og i statusbaren. `INFO` er bare informasjon, `WARN` er noe å sjekke, `FAIL` er kritisk.


### Kontroll og sløyfe

- **`Kontrollsløyfe startet` / `stoppet`** — Start- eller Stopp-knappen er trykket.
- **`Kontroll-tråd kræsjet: ...`** — Et uventet unntak i styringssløyfen. Hele tracebacken skrives til terminalen — sjekk der for detaljer. E-STOP utløses automatisk.
- **`Polling-feil: ...`** — En av snapshot-avlesningene feilet (kan komme av feil med I2C). Workeren kjører videre, men hvis det kommer ofte er det noe galt med bussen.


### Sikkerhet

- **`E-STOP: <grunn>`** — Nødstopp utløst. Servoene er frikoblet. Reset i Sikkerhet-fanen.
- **`[CRITICAL] <brudd>`** — Sikkerhetsbrudd som utløste E-STOP (f.eks. servovinkel utenfor grense).
- **`[WARNING] <brudd>`** — Mindre alvorlig brudd, sløyfen kjører videre, men noter det.
- **`E-STOP tilbakestilt`** — Bruker har kvittert feilen.


### Konfig

- **`Stopp kontrollsløyfen før konfigurasjonen kan endres`** — Kan ikke laste ny config mens sløyfen kjører. Trykk Stopp først.
- **`Reinit feilet: ...`** — Ny config var gyldig, men hardware-init feilet etter omstart. Sjekk I2C-adresser og kabling.
- **`Konfigurasjon aktivert`** — Ny config er i bruk, hele domenet er bygget på nytt.
- **`Konfigurasjon lagret til default_config.yaml`** — YAML-fil er skrevet.


### Knapper

- **`Knappe-feil: ...`** — Knappekortet svarer ikke (I2C-feil eller GPIO ikke tilgjengelig). GUI-et fungerer videre uten knappekort.
- **`[knappekort] kunne ikke åpne GPIO`** / **`I2C`** — Står i terminalen ved oppstart, betyr at knappe-driveren ikke ble lastet. GUI starter uten knappestøtte.


### IMU

- **`Gyro-kalibrering fullført`** — OK, biasen er lagret.
- **`Gyro-kalibrering er ikke implementert i driveren`** — Driveren mangler `calibrate_gyro_bias()`. Ikke en feil i GUI-et.
- **`Gyro-kalibrering feilet: ...`** — IMU svarte ikke, eller noe annet gikk galt under kalibrering.



## Hurtigtaster

- `F1` — E-STOP
- `F2` — lang-trykk midt (E-STOP via knappemodellen)
- Piltaster — naviger mellom widgets
- `Enter` — aktiver/bekreft
