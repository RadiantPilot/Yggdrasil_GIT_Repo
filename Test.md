# Yggdrasil GUI · Implementasjonsplan

Dokumentet beskriver struktur, avhengigheter og byggerekkefølge for GUI-et
til Stewart-plattformen (prosjekt AUT-2606).

---

## 1. Teknologivalg

| Komponent | Valg | Begrunnelse |
|---|---|---|
| GUI-rammeverk | **PySide6** (Qt 6) | Native widgets, signal/slot matcher observer-pattern, LGPL |
| Plot / grafer | **pyqtgraph** | 100+ Hz sanntidsplot, laget for vitenskapelig bruk |
| 3D-visualisering | **pyqtgraph.opengl** eller `QOpenGLWidget` | Lettvekts 3D direkte i Qt |
| Tråding | **QThread** + signals | Isolerer kontroll-loop fra GUI-loop |
| Tabellredigering | `QTableView` + `QAbstractTableModel` | Binder mot dataclasses |
| Stil | Qt Style Sheet (QSS) | Enkelt å tema-støtte (lys/mørk) |

**Installer:**
```bash
pip install PySide6 pyqtgraph numpy PyYAML
```

---

## 2. Arkitekturprinsipper

1. **GUI rører aldri hardware direkte.** All kommunikasjon mot
   `stewart_platform`-pakkene går gjennom `controller_bridge.py` som
   oversetter Qt-signaler til kall mot kontroll-objektene.
2. **Kontroll-loopen eier sannheten.** GUI er en leser/viewer; når
   brukeren justerer noe sendes det som en forespørsel, og GUI
   oppdaterer seg først når kontroll-loopen rapporterer ny tilstand.
3. **Snapshot-oppdatering.** Kontroll-loopen emitterer én `StateSnapshot`
   (dataclass) per tick med all relevant tilstand. GUI forbruker dette
   og ruter til riktige widgets.
4. **Validering skjer i domenet, ikke i GUI.** GUI sender ønsket
   verdi, `stewart_platform` aksepterer eller avviser med begrunnelse.
5. **Tabs er uavhengige.** Hver tab er egen `QWidget`-subklass — kan
   testes isolert og byttes ut uten å påvirke resten.

---

## 3. Mappestruktur

```
yggdrasil/
├── GUI_PLAN.md                      # dette dokumentet
├── gui/
│   ├── __init__.py
│   ├── app.py                       # inngangspunkt: skaper QApplication
│   ├── main_window.py               # QMainWindow med 6-tabs QTabWidget
│   │
│   ├── bridge/
│   │   ├── __init__.py
│   │   ├── controller_bridge.py     # eneste tilkobling GUI ↔ stewart_platform
│   │   ├── state_snapshot.py        # @dataclass StateSnapshot
│   │   └── polling_worker.py        # QThread som henter snapshots
│   │
│   ├── tabs/
│   │   ├── __init__.py
│   │   ├── base_tab.py              # felles QWidget-base for alle tabs
│   │   ├── overview_tab.py          # Tab 1: Oversikt
│   │   ├── pose_control_tab.py      # Tab 2: Pose-kontroll
│   │   ├── pid_tuning_tab.py        # Tab 3: PID-tuning (6 sett)
│   │   ├── imu_tab.py               # Tab 4: IMU
│   │   ├── config_tab.py            # Tab 5: Konfigurasjon
│   │   └── safety_tab.py            # Tab 6: Sikkerhet
│   │
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── pose_sliders.py          # 6-DOF slider-panel m/numerisk input
│   │   ├── pid_card.py              # Kp/Ki/Kd sliders for én akse
│   │   ├── servo_bars.py            # horisontale bar-grafer for 6 servoer
│   │   ├── indicator_lamp.py        # fargelampe m/tekst
│   │   ├── realtime_plot.py         # wrapper rundt pyqtgraph med rullerende vindu
│   │   ├── platform_3d.py           # 3D-visning av plattform (OpenGL)
│   │   ├── response_plot.py         # step-respons-graf m/metrikk-overlegg
│   │   ├── servo_config_table.py    # editerbar QTableView for 6 servoer
│   │   ├── status_banner.py         # stor statusbanner øverst på tabs
│   │   └── event_log.py             # rullerende hendelsesliste
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── servo_table_model.py     # QAbstractTableModel for servo-config
│   │   └── event_log_model.py       # QAbstractTableModel for logg
│   │
│   ├── style/
│   │   ├── __init__.py
│   │   ├── theme.py                 # fargepaletter og typografi-konstanter
│   │   ├── light.qss                # lys tema (QSS)
│   │   └── dark.qss                 # mørk tema (QSS)
│   │
│   └── utils/
│       ├── __init__.py
│       ├── ring_buffer.py           # numpy-basert rullerende vindu for plots
│       └── formatting.py            # fmt_mm, fmt_deg, fmt_time, etc.
│
└── tests/
    └── test_gui_*.py                 # GUI-tester (pytest-qt)
```

---

## 4. Byggerekkefølge (iterativt, hver fase kjørbar)

**Fase 1 · Skjelett**
1. `app.py`, `main_window.py` — tomt vindu med 6 tabs (bare titler)
2. `bridge/state_snapshot.py` — definer dataclassen
3. `bridge/controller_bridge.py` — stub med dummy-data
4. `bridge/polling_worker.py` — QThread som emitterer snapshots @ 30 Hz

**Fase 2 · Kritiske tabs**
5. `widgets/pid_card.py` + `tabs/pid_tuning_tab.py` (hovedbruken)
6. `widgets/realtime_plot.py`, `widgets/response_plot.py`
7. `widgets/pose_sliders.py` + `tabs/pose_control_tab.py`

**Fase 3 · Resten**
8. `tabs/overview_tab.py` (bruker widgets fra fase 2)
9. `tabs/imu_tab.py`
10. `tabs/safety_tab.py` — kritisk for sikkerhet
11. `tabs/config_tab.py` — sist fordi den er minst kritisk

**Fase 4 · Polering**
12. Styling (`style/`)
13. 3D-visualisering (`widgets/platform_3d.py`)
14. Tester

---

## 5. Kontrakt mot `stewart_platform`

Alle kontraktskrav nedenfor er implementert og testet (252 tester).
Signaturer her matcher eksisterende domene-kode.

### `MotionController`
- `get_current_pose() -> Pose`
- `target_pose -> Pose`  (property)
- `set_target_pose(pose: Pose) -> bool`  (returnerer False ved avvist pose)
- `start()`, `stop()`, `home()`, `emergency_stop()`, `shutdown()`
- `is_running() -> bool`
- `get_servo_angles() -> list[float]`
- Properties: `pose_controller`, `safety_monitor`, `imu_fusion`, `base_imu`, `servo_array`

### `PoseController`
- `get_pid_gains(axis: Axis) -> PIDGains`  (Axis = X/Y/Z/ROLL/PITCH/YAW, IntEnum i config)
- `set_pid_gains(axis: Axis, gains: PIDGains) -> None`
- `set_gains(gains: PIDGains) -> None`  (alle 6 akser)
- `trigger_step_response(axis: Axis, from_val: float, to_val: float) -> None`
- `get_step_response_recorder(axis: Axis) -> StepResponseRecorder | None`
- `add_response_listener(callback) -> None`  (callback: (Axis, float, float, float))
- `remove_response_listener(callback) -> None`

### `StepResponseRecorder`
- `axis: Axis`, `from_val: float`, `to_val: float`, `is_active: bool`
- `samples: list[tuple[float, float, float]]`  (timestamp, setpoint, actual)
- `record(timestamp, setpoint, actual) -> None`
- `finish() -> None`

### `IMUInterface` (abstrakt)
- `read_acceleration() -> Vector3`
- `read_angular_velocity() -> Vector3`
- `read_temperature() -> float`
- `calibrate_gyro_bias() -> None`
- `calibrate_accelerometer_offset() -> None`
- Orientering hentes fra `IMUFusion.get_orientation() -> Vector3` (roll, pitch, yaw)

### `ServoArray`
- `get_angles() -> list[float]`  (6 verdier)
- `get_servo_configs() -> list[ServoConfig]`
- `set_servo_config(idx: int, cfg: ServoConfig) -> bool`
- `set_angles(angles: list[float]) -> None`
- `go_home() -> None`, `detach_all() -> None`
- `validate_angles(angles: list[float]) -> bool`

### `SafetyMonitor`
- `trigger_e_stop(reason: str = "") -> None`
- `is_e_stopped() -> bool`
- `e_stop_reason -> str | None`  (property)
- `reset_latched_faults() -> bool`
- `get_limits() -> SafetyConfig`
- `set_limits(config: SafetyConfig) -> None`
- `get_check_results() -> list[SafetyCheckResult]`  (siste 100)
- `check_all(pose, angles, accel, dt) -> SafetyCheckResult`
- `validate_pose(pose) -> bool`, `validate_servo_angles(angles) -> bool`

### `PlatformConfig`
- `load(filepath) -> PlatformConfig`, `save(filepath) -> None`
- `validate() -> list[str]`  (tom liste = gyldig)
- `raise_if_invalid() -> None`  (kaster ValueError)

---

## 6. Tråd-modell

```
┌──────────────────────┐        ┌──────────────────────┐
│  Main thread (Qt)    │        │ ControlLoop thread   │
│  - GUI event loop    │◄──────►│ - 100 Hz kontroll    │
│  - tegner widgets    │ signals│ - leser IMU, styrer  │
└──────────┬───────────┘        │   servoer            │
           │ QThread            └──────────┬───────────┘
           ▼                               │
┌──────────────────────┐                   │
│ PollingWorker        │ ◄─────────────────┘
│ - leser snapshot @   │   (shared state eller queue)
│   30 Hz              │
│ - emit snapshotReady │
└──────────────────────┘
```

GUI må **aldri** blokkere på I/O eller kontroll-loopen.

---

## 7. Åpne spørsmål for senere

- Skal GUI kunne kjøre uten hardware (simulert modus)? Anbefaler ja —
  `ControllerBridge` får en `--mock` flag.
- Logging til fil (CSV?) for step-respons-data — egen modul senere.
- Auto-tune (Ziegler–Nichols) som knapp i PID-tab — nice-to-have.
- Multi-preset-håndtering for pose-kontroll — lagres hvor?
