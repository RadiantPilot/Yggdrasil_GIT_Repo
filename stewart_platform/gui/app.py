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

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QApplication

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
        default=30.0,
        help="Oppdateringsfrekvens for GUI-polling i Hz (default 30).",
    )
    parser.add_argument(
        "--theme",
        choices=["light", "dark"],
        default="light",
        help="Startstema for GUI-et (kan byttes i toppmenyen).",
    )
    return parser.parse_args()


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
    window.show()

    worker_thread.start()

    # Ryddig nedkobling når Qt lukker
    def _shutdown() -> None:
        worker.stop()
        worker_thread.quit()
        worker_thread.wait(2000)
        bridge.shutdown()

    app.aboutToQuit.connect(_shutdown)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
