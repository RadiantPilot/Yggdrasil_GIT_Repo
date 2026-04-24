"""
polling_worker.py · QObject som kjører på egen tråd og emitterer
StateSnapshot med jevn frekvens.

PollingWorker skal ikke blokkere GUI-tråden. Den kjører på en
QThread (se app.py) og bruker en intern stopp-flagg for ryddig
avslutning. Signaler fra Qt er trådtrygge.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal, Slot

from .controller_bridge import ControllerBridge
from .state_snapshot import StateSnapshot


class PollingWorker(QObject):
    """Henter StateSnapshot fra ControllerBridge og emitterer det."""

    snapshot_ready = Signal(object)  # emit StateSnapshot

    def __init__(self, bridge: ControllerBridge, rate_hz: float = 30.0) -> None:
        super().__init__()
        self._bridge = bridge
        self._rate_hz = max(1.0, rate_hz)
        self._stop = False

    @Slot()
    def run(self) -> None:
        """Tråd-hovedløkke. Sluttet av stop() fra GUI-tråden."""
        period = 1.0 / self._rate_hz
        next_tick = time.monotonic()
        while not self._stop:
            snapshot: StateSnapshot = self._bridge.get_snapshot()
            self.snapshot_ready.emit(snapshot)

            next_tick += period
            now = time.monotonic()
            sleep_for = next_tick - now
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # Vi henger etter — resynkroniser så vi ikke brenner CPU
                next_tick = now

    def stop(self) -> None:
        """Signaliser ryddig stopp. Trådtrygg."""
        self._stop = True
