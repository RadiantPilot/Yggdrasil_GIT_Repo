"""
polling_worker.py · QObject som kjører på egen tråd og emitterer
StateSnapshot med jevn frekvens.

PollingWorker skal ikke blokkere GUI-tråden. Den kjører på en
QThread (se app.py) og bruker en threading.Event for ryddig
avslutning. Signaler fra Qt er trådtrygge.
"""

from __future__ import annotations

import logging
import threading
import time

from PySide6.QtCore import QObject, Signal, Slot

from .controller_bridge import ControllerBridge
from .state_snapshot import StateSnapshot

_log = logging.getLogger(__name__)


class PollingWorker(QObject):
    """Henter StateSnapshot fra ControllerBridge og emitterer det.

    error_occurred sendes hvis bridge.get_snapshot() kaster — GUI-en
    kan da vise en feilmelding i status-banner istedenfor å vise
    stillstand uten varsel. Tråden fortsetter å kjøre og prøver
    igjen ved neste tick.
    """

    snapshot_ready = Signal(object)  # emit StateSnapshot
    error_occurred = Signal(str)     # emit feilmelding

    def __init__(self, bridge: ControllerBridge, rate_hz: float = 30.0) -> None:
        super().__init__()
        self._bridge = bridge
        self._rate_hz = max(1.0, rate_hz)
        self._stop_event = threading.Event()

    @Slot()
    def run(self) -> None:
        """Tråd-hovedløkke. Sluttet av stop() fra GUI-tråden."""
        period = 1.0 / self._rate_hz
        next_tick = time.monotonic()
        while not self._stop_event.is_set():
            try:
                snapshot: StateSnapshot = self._bridge.get_snapshot()
                self.snapshot_ready.emit(snapshot)
            except Exception as exc:  # noqa: BLE001 — vil fange alt
                # Fang alle ikke-system feil og hold tråden i live.
                # GUI-en får varselet via error_occurred-signalet.
                _log.exception("PollingWorker tick failed")
                self.error_occurred.emit(str(exc))

            next_tick += period
            wait = next_tick - time.monotonic()
            if wait > 0:
                # Event.wait gjør stop() responsiv — vi venter med
                # event-en i stedet for time.sleep slik at avslutning
                # ikke blir forsinket av et nettopp-startet sleep.
                if self._stop_event.wait(timeout=wait):
                    return
            else:
                # Vi henger etter — resynkroniser så vi ikke brenner CPU
                next_tick = time.monotonic()

    def stop(self) -> None:
        """Signaliser ryddig stopp. Trådtrygg."""
        self._stop_event.set()
