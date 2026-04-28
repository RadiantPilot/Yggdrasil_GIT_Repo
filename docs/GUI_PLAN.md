# Yggdrasil GUI - Implementasjonsplan

Dokumentet beskriver struktur, avhengigheter og byggerekkefølge for GUI-et
til Stewart-plattformen (prosjekt AUT-2606).

---

## 1. Teknologivalg

| Komponent | Valg | Begrunnelse |
|---|---|---|
| GUI-rammeverk | **PySide6** (Qt 6) | Native widgets, signal/slot passer godt med observer-pattern, LGPL |
| Plot / grafer | **pyqtgraph** | Rask nok til sanntidsplot på 100+ Hz |
| 3D-visualisering | **pyqtgraph.opengl** eller `QOpenGLWidget` | Lett 3D direkte i Qt |
| Tråding | **QThread** + signals | Skiller kontroll-loop fra GUI-loop |
| Tabellredigering | `QTableView` + `QAbstractTableModel` | Binder mot dataclasses |
| Stil | Qt Style Sheet (QSS) | Lett å lage tema (lys/mørk) |

**Installer:**
```bash
pip install PySide6 pyqtgraph numpy PyYAML
```

---

## 2. Arkitekturprinsipper

1. **GUI snakker aldri direkte med hardware.** All kommunikasjon mot
   `stewart_platform`-pakkene går gjennom `controller_bridge.py`, som
   oversetter Qt-signaler til kall mot kontroll-objektene.
2. **Kontroll-loopen er sjefen.** GUI er bare en viewer. Når
   brukeren justerer noe, sendes det som en forespørsel, og GUI
   oppdaterer seg først når kontroll-loopen rapporterer ny tilstand.
3. **Snapshot-oppdatering.** Kontroll-loopen sender ut én `StateSnapshot`
   (dataclass) per tick med all relevant tilstand. GUI tar imot dette
   og fordeler det til riktige widgets.
4. **Validering skjer i domenet, ikke i GUI.** GUI sender ønsket
   verdi, og `stewart_platform` aksepterer eller avviser med begrunnelse.
5. **Tabs er uavhengige.** Hver tab er en egen `QWidget`-subklasse, og
   kan testes isolert og byttes ut uten å påvirke resten.

---

## 3. Mappestruktur

```
stewart_platform/gui/
├── __init__.py
├── __main__.py
├── app.py                       # inngangspunkt: lager QApplication
├── main_window.py               # QMainWindow med 6-tabs QTabWidget
│
├── bridge/
│   ├── __init__.py
│   ├── controller_bridge.py     # eneste kobling mellom GUI og stewart_platform
│   ├── state_snapshot.py        # @dataclass StateSnapshot
│   └── polling_worker.py        # QThread som henter snapshots
│
└── tabs/
    ├── __init__.py
    ├── base_tab.py              # felles QWidget-base for alle tabs
    ├── overview_tab.py          # Tab 1: Oversikt
    ├── pose_control_tab.py      # Tab 2: Pose-kontroll
    ├── pid_tuning_tab.py        # Tab 3: PID-tuning (6 sett)
    ├── imu_tab.py               # Tab 4: IMU
    ├── config_tab.py            # Tab 5: Konfigurasjon
    └── safety_tab.py            # Tab 6: Sikkerhet
```

Senere faser vil legge til:
```
    ├── widgets/                 # gjenbrukbare widgets (pid_card, pose_sliders, osv.)
    ├── models/                  # Qt table-modeller
    ├── style/                   # tema (QSS, fargepaletter)
    └── utils/                   # ring_buffer, formatering
```

---

## 4. Byggerekkefølge (iterativt, hver fase kjørbar)

**Fase 1: Skjelett** ✅
1. `app.py`, `main_window.py`: vindu med 6 tabs (placeholder)
2. `bridge/state_snapshot.py`: definer dataclassen
3. `bridge/controller_bridge.py`: ekte modus + mock-modus
4. `bridge/polling_worker.py`: QThread som sender snapshots på 30 Hz

**Fase 2: Kritiske tabs**
5. `widgets/pid_card.py` + `tabs/pid_tuning_tab.py` (hovedbruken)
6. `widgets/realtime_plot.py`, `widgets/response_plot.py`
7. `widgets/pose_sliders.py` + `tabs/pose_control_tab.py`

**Fase 3: Resten**
8. `tabs/overview_tab.py` (bruker widgets fra fase 2)
9. `tabs/imu_tab.py`
10. `tabs/safety_tab.py`: viktig for sikkerhet
11. `tabs/config_tab.py`: sist fordi den er minst kritisk

**Fase 4: Polering**
12. Styling (`style/`)
13. 3D-visualisering (`widgets/platform_3d.py`)
14. Tester

---

## 5. Kontrakt mot `stewart_platform`

For at GUI skal fungere må følgende være tilgjengelig. ✅ = implementert.

### `MotionController` ✅
- `get_current_pose() -> Pose`
- `get_target_pose() -> Pose` (via `target_pose` property)
- `set_target_pose(pose: Pose) -> bool`
- `start()`, `stop()`, `home()`
- `is_running() -> bool`
- `emergency_stop()`
- `get_servo_angles() -> list[float]`

### `PoseController` ✅
- `get_pid_gains(axis: Axis) -> PIDGains`
- `set_pid_gains(axis: Axis, gains: PIDGains) -> None`
- `trigger_step_response(axis: Axis, from_val: float, to_val: float) -> None`
- `get_step_response_recorder(axis) -> StepResponseRecorder`
- `add_response_listener(callback)` / `remove_response_listener(callback)`

### `IMUInterface` ✅
- `read_acceleration() -> Vector3`
- `read_angular_velocity() -> Vector3`
- `calibrate_gyro_bias()`
- `calibrate_accelerometer_offset()`

### `ServoArray` ✅
- `get_angles() -> list[float]`
- `get_servo_configs() -> list[ServoConfig]`
- `set_servo_config(idx: int, cfg: ServoConfig) -> bool`

### `SafetyMonitor` ✅
- `get_check_results() -> list[SafetyCheckResult]`
- `is_e_stopped() -> bool`
- `trigger_e_stop(reason: str)`
- `reset_latched_faults() -> bool`
- `get_limits() -> SafetyConfig`
- `set_limits(cfg: SafetyConfig) -> None`
- `e_stop_reason` property

### `PlatformConfig` ✅
- `load()` / `save()` (YAML)
- `validate() -> list[str]`
- `raise_if_invalid()`

---

## 6. Tråd-modell

```
┌──────────────────────┐        ┌──────────────────────┐
│  Main thread (Qt)    │        │ ControlLoop thread   │
│  - GUI event loop    │<──────>│ - 100 Hz kontroll    │
│  - tegner widgets    │ signals│ - leser IMU, styrer  │
└──────────┬───────────┘        │   servoer            │
           │ QThread            └──────────┬───────────┘
           v                               │
┌──────────────────────┐                   │
│ PollingWorker        │ <─────────────────┘
│ - leser snapshot på  │   (delt state eller queue)
│   30 Hz              │
│ - emit snapshotReady │
└──────────────────────┘
```

GUI skal **aldri** blokkere på I/O eller kontroll-loopen.

---

## 7. Åpne spørsmål for senere

- Skal GUI kunne kjøre uten hardware (simulert modus)? ✅ Ja, med `--mock` flag.
- Logging til fil (CSV?) for step-respons-data: egen modul senere.
- Auto-tune (Ziegler-Nichols) som knapp i PID-tab: nice-to-have.
- Multi-preset-håndtering for pose-kontroll: hvor skal disse lagres?
