"""
button_worker.py · QObject som poller ButtonInterface på egen tråd
og emitterer Qt-signaler ved press, slipp og lang-trykk.

Worker-en gjør:
  1. Polling med konfigurerbar frekvens.
  2. Debouncing — krever stabil avlesning over debounce_ms før
     en endring rapporteres.
  3. Lang-trykk-deteksjon — separat signal hvis en knapp holdes
     lengre enn long_press_ms (først rapportert ved slipp, så
     vanlig button_released uteblir for lang-trykk).

Signalene plukkes opp av FocusManager på GUI-tråden.
"""

from __future__ import annotations

import logging
import threading
import time

from PySide6.QtCore import QObject, Signal, Slot

from ...hardware.button_interface import ButtonInterface

_log = logging.getLogger(__name__)


class ButtonWorker(QObject):
    """Trådbasert poller for det fysiske knappekortet.

    Knappeindeksene 0..4 følger samme konvensjon som
    ButtonInterface: 0 = knapp 1 (venstre), 1 = knapp 2 (opp),
    2 = knapp 3 (midt), 3 = knapp 4 (ned), 4 = knapp 5 (høyre).

    error_occurred sendes hvis driveren kaster en uventet feil
    (annet enn forbigående I2C-glitch). Tråden fortsetter å kjøre.
    """

    button_pressed = Signal(int)
    button_released = Signal(int)
    button_long_pressed = Signal(int)
    error_occurred = Signal(str)

    def __init__(
        self,
        driver: ButtonInterface,
        poll_hz: float = 50.0,
        debounce_ms: float = 20.0,
        long_press_ms: float = 1000.0,
    ) -> None:
        """Opprett worker.

        Args:
            driver: Konkret ButtonInterface-implementasjon.
            poll_hz: Pollefrekvens.
            debounce_ms: Stabilitetsvindu for debouncing.
            long_press_ms: Hvor lenge en knapp må holdes for at
                button_long_pressed skal emitteres.
        """
        super().__init__()
        self._driver = driver
        self._period = 1.0 / max(1.0, poll_hz)
        self._debounce_s = max(0.0, debounce_ms) / 1000.0
        self._long_press_s = max(0.0, long_press_ms) / 1000.0
        self._stop_event = threading.Event()

        n = ButtonInterface.NUM_BUTTONS
        # Sist rapporterte stabile tilstand per knapp (True = trykket).
        self._stable: list[bool] = [False] * n
        # Sist sett rå-avlesning per knapp og tidspunkt for endring.
        self._last_raw: list[bool] = [False] * n
        self._last_change_t: list[float] = [0.0] * n
        # Tidspunkt da knappen gikk fra sluppet til trykket (stabil).
        self._press_start_t: list[float] = [0.0] * n
        # Hvorvidt lang-trykk allerede er emittert for nåværende press.
        self._long_emitted: list[bool] = [False] * n

    @Slot()
    def run(self) -> None:
        """Tråd-hovedløkke. Sluttet av stop() fra GUI-tråden."""
        next_tick = time.monotonic()
        while not self._stop_event.is_set():
            now = time.monotonic()
            self._tick(now)

            next_tick += self._period
            wait = next_tick - time.monotonic()
            if wait > 0:
                # Event-basert venting — stop() blir responsiv.
                if self._stop_event.wait(timeout=wait):
                    return
            else:
                next_tick = time.monotonic()

    def _tick(self, now: float) -> None:
        """Én pollesyklus. Skilt ut for testbarhet."""
        try:
            mask = self._driver.read()
        except OSError:
            # Forbigående I2C-feil — hopp over denne syklusen og
            # prøv igjen ved neste tick. Logges ikke for å unngå
            # spam hvis bussen er borte over lengre tid.
            return
        except Exception as exc:  # noqa: BLE001 — bevare tråden
            # Andre uventede driverfeil (programmeringsfeil,
            # Argon-ressurs som forsvant, …) skal ikke drepe
            # workeren stille. Varsle GUI og fortsett — neste
            # tick prøver igjen.
            _log.exception("ButtonWorker tick failed")
            self.error_occurred.emit(str(exc))
            return

        for i in range(ButtonInterface.NUM_BUTTONS):
            raw = bool(mask & (1 << i))

            if raw != self._last_raw[i]:
                self._last_raw[i] = raw
                self._last_change_t[i] = now
                continue

            # Råverdien har vært stabil — sjekk om vi skal forfremme
            # den til ny rapportert tilstand.
            stable_for = now - self._last_change_t[i]
            if raw != self._stable[i] and stable_for >= self._debounce_s:
                self._stable[i] = raw
                if raw:
                    self._press_start_t[i] = now
                    self._long_emitted[i] = False
                    self.button_pressed.emit(i)
                else:
                    if not self._long_emitted[i]:
                        self.button_released.emit(i)

            # Lang-trykk: sjekk hvis knappen er stabilt trykket og
            # vi ikke allerede har emittert lang-trykk for denne
            # press-syklusen.
            if (
                self._stable[i]
                and not self._long_emitted[i]
                and (now - self._press_start_t[i]) >= self._long_press_s
            ):
                self._long_emitted[i] = True
                self.button_long_pressed.emit(i)

    def stop(self) -> None:
        """Signaliser ryddig stopp. Trådtrygg."""
        self._stop_event.set()
