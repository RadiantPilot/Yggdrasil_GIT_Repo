# mock_buttons.py
# ===============
# Mock-implementasjon av ButtonInterface for tester og GUI-utvikling
# uten fysisk hardware. Knappestatus settes manuelt fra utsiden
# (f.eks. via tastatur-shortcuts i GUI-en) og leses tilbake av
# ButtonWorker som om det var ekte hardware.

from __future__ import annotations

import threading

from .button_interface import ButtonInterface


class MockButtons(ButtonInterface):
    """Mock-driver der knappestatus settes programmatisk.

    Brukes i to sammenhenger:
      1. Enhetstester — testkoden setter bit-mønstre direkte.
      2. GUI-utvikling på dev-PC — piltaster + Enter mappes til
         press()/release() av MainWindow, slik at hele
         navigasjonssystemet kan utvikles uten knappekort.

    Tråd-trygt: read() og press()/release() kan kalles fra
    forskjellige tråder (ButtonWorker leser, GUI-tråden skriver).
    """

    def __init__(self) -> None:
        """Opprett en mock-driver med alle knapper utløst."""
        self._state = 0
        self._lock = threading.Lock()
        self._closed = False

    def read(self) -> int:
        """Les nåværende knappestatus som bitmaske."""
        with self._lock:
            return self._state

    def press(self, button_index: int) -> None:
        """Marker en knapp som trykket.

        Args:
            button_index: 0..4 (knapp 1..5).
        """
        if not 0 <= button_index < self.NUM_BUTTONS:
            raise ValueError(
                f"button_index må være i [0, {self.NUM_BUTTONS}), fikk {button_index}"
            )
        with self._lock:
            self._state |= 1 << button_index

    def release(self, button_index: int) -> None:
        """Marker en knapp som sluppet.

        Args:
            button_index: 0..4 (knapp 1..5).
        """
        if not 0 <= button_index < self.NUM_BUTTONS:
            raise ValueError(
                f"button_index må være i [0, {self.NUM_BUTTONS}), fikk {button_index}"
            )
        with self._lock:
            self._state &= ~(1 << button_index)

    def set_state(self, mask: int) -> None:
        """Sett hele bitmasken på én gang. Nyttig i tester."""
        with self._lock:
            self._state = mask & ((1 << self.NUM_BUTTONS) - 1)

    def close(self) -> None:
        """Marker mock-driveren som lukket. Idempotent."""
        with self._lock:
            self._closed = True
            self._state = 0
