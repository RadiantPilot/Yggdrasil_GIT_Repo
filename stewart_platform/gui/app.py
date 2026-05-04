"""
app.py · Inngangspunkt for GUI-applikasjonen.

Opprett QApplication, parse argumenter, instansier ControllerBridge
(ekte eller mock), start PollingWorker og åpne MainWindow. Sørg for
ryddig nedkobling ved exit.

Kjøres som:
    python -m stewart_platform.gui                    # ekte hardware
    python -m stewart_platform.gui --mock             # simulert
    python -m stewart_platform.gui --config PATH      # alternativ YAML
    python -m stewart_platform.gui --rate 30          # polling-rate (Hz)
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QApplication

# Globale pyqtgraph-innstillinger må settes før noen PlotWidget bygges.
# Antialiasing og OpenGL er begge ekstremt dyre på Pi 4B uten GPU —
# sett dem av eksplisitt for å gi deterministisk, lett rendering.
pg.setConfigOptions(antialias=False, useOpenGL=False)

from ..config.button_config import ButtonConfig
from ..hardware.button_interface import ButtonInterface
from .bridge.button_worker import ButtonWorker
from .bridge.controller_bridge import ControllerBridge
from .bridge.polling_worker import PollingWorker
from .main_window import MainWindow
from .utils.theme import DARK, LIGHT, ThemeManager


def _parse_args() -> argparse.Namespace:
    """Parse kommandolinje-argumenter."""
    parser = argparse.ArgumentParser(
        description="Yggdrasil GUI — Stewart-plattform kontrollgrensesnitt",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Kjør i simulert modus uten å snakke med hardware.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/default_config.yaml"),
        help="Sti til YAML-konfigurasjonsfil.",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=8.0,
        help="Oppdateringsfrekvens for GUI-polling i Hz (default 8).",
    )
    parser.add_argument(
        "--theme",
        choices=["light", "dark"],
        default="dark",
        help="Startstema for GUI-et (kan byttes i toppmenyen).",
    )
    return parser.parse_args()


def _build_button_driver(
    cfg: ButtonConfig,
    bridge: ControllerBridge,
) -> ButtonInterface | None:
    """Velg riktig ButtonInterface-implementasjon basert på config.

    Returnerer None hvis knappene er deaktivert eller hvis valgt
    backend ikke kan initialiseres (loggføres som advarsel).
    """
    if not cfg.enabled:
        return None

    backend = cfg.backend.lower()

    if backend == "mock" or bridge.is_mock:
        from ..hardware.mock_buttons import MockButtons
        return MockButtons()

    if backend == "gpio":
        try:
            from ..hardware.rpi_gpio_buttons import RPiGPIOButtons
            return RPiGPIOButtons(cfg.gpio_pins)
        except (ImportError, OSError) as exc:
            print(f"[knappekort] kunne ikke åpne GPIO: {exc}", file=sys.stderr)
            return None

    if backend == "i2c":
        try:
            # Import lazy så dev-PC uten smbus2 ikke faller på import-tid
            from ..hardware.attiny_i2c_buttons import AttinyI2CButtons
            from ..hardware.i2c_bus import I2CBus
            bus = I2CBus(bridge.config.i2c_bus_number)
            return AttinyI2CButtons(
                bus,
                address=cfg.i2c_address,
                button_bits=cfg.i2c_button_bits,
            )
        except (ImportError, OSError) as exc:
            print(f"[knappekort] kunne ikke åpne I2C: {exc}", file=sys.stderr)
            return None

    print(f"[knappekort] ukjent backend: {cfg.backend}", file=sys.stderr)
    return None


def main() -> int:
    """Kjør GUI-applikasjonen.

    Returns:
        Exit-kode fra Qt event-loopen.
    """
    args = _parse_args()

    # Tillat Ctrl+C fra terminalen også når Qt event-loop kjører
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("Yggdrasil")
    app.setOrganizationName("AUT-2606")

    # Tema må settes før plot-widgets konstrueres, slik at pyqtgraphs
    # globale bakgrunns-/forgrunnsdefault treffer fra starten av.
    ThemeManager.instance().apply(DARK if args.theme == "dark" else LIGHT)

    # Bygg bridge — mock hvis flagget er satt, ellers ekte hardware
    bridge = ControllerBridge(config_path=args.config, mock=args.mock)
    bridge.initialize()

    # Start polling-worker på egen tråd
    worker_thread = QThread()
    worker_thread.setObjectName("YggdrasilPollingThread")
    worker = PollingWorker(bridge, rate_hz=args.rate)
    worker.moveToThread(worker_thread)
    worker_thread.started.connect(worker.run)

    # Hovedvindu
    window = MainWindow(bridge)
    worker.snapshot_ready.connect(window.on_snapshot, Qt.QueuedConnection)
    # Polling-feil (f.eks. midlertidig I2C-glitch) logges som event
    # slik at brukeren ser at noe er galt — workeren kjører videre.
    worker.error_occurred.connect(
        lambda msg: bridge._log_event("FAIL", f"Polling-feil: {msg}"),
        Qt.QueuedConnection,
    )
    window.show()

    worker_thread.start()

    # Knappekort: bygg driver, ButtonWorker og koble til FocusManager
    button_driver = _build_button_driver(bridge.config.button_config, bridge)
    button_thread: QThread | None = None
    button_worker: ButtonWorker | None = None
    if button_driver is not None:
        bcfg = bridge.config.button_config
        button_worker = ButtonWorker(
            driver=button_driver,
            poll_hz=bcfg.poll_hz,
            debounce_ms=bcfg.debounce_ms,
            long_press_ms=bcfg.long_press_ms,
        )
        button_thread = QThread()
        button_thread.setObjectName("YggdrasilButtonThread")
        button_worker.moveToThread(button_thread)
        button_thread.started.connect(button_worker.run)
        button_worker.button_pressed.connect(
            window.focus_manager.on_pressed, Qt.QueuedConnection
        )
        button_worker.button_long_pressed.connect(
            window.focus_manager.on_long_pressed, Qt.QueuedConnection
        )
        button_worker.error_occurred.connect(
            lambda msg: bridge._log_event("FAIL", f"Knappe-feil: {msg}"),
            Qt.QueuedConnection,
        )
        button_thread.start()

    # Ryddig nedkobling når Qt lukker
    def _shutdown() -> None:
        if button_worker is not None:
            button_worker.stop()
        if button_thread is not None:
            button_thread.quit()
            button_thread.wait(2000)
        if button_driver is not None:
            button_driver.close()
        worker.stop()
        worker_thread.quit()
        worker_thread.wait(2000)
        bridge.shutdown()

    app.aboutToQuit.connect(_shutdown)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
