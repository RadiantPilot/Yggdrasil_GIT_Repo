# rpi_gpio_buttons.py
# ===================
# Konkret ButtonInterface-implementasjon som leser de fem
# knappene direkte fra Raspberry Pi sine GPIO-pinner via gpiozero.
# Bruker intern pull-up siden knappene er passive til GND.

from __future__ import annotations

from typing import List

from .button_interface import ButtonInterface


class RPiGPIOButtons(ButtonInterface):
    """Leser knappekortet via direkte GPIO-tilkobling.

    Hver knapp er koblet mellom GPIO-pin og GND. Med intern
    pull-up er pinnen høy i ro og lav når knappen trykkes,
    derfor speiles is_pressed til bit 1.

    Implementasjonen er bevisst stateless — gpiozero håndterer
    selve pin-tilstanden, og read() bare aggregerer is_pressed
    fra de 5 Button-objektene til en bitmaske.
    """

    def __init__(self, gpio_pins: List[int]) -> None:
        """Opprett driveren og initialiser GPIO-pinnene.

        Args:
            gpio_pins: BCM-numre for de 5 knappene, i rekkefølge
                knapp 1..5. Må ha lengde lik NUM_BUTTONS.

        Raises:
            ValueError: Hvis listen har feil lengde.
            ImportError: Hvis gpiozero ikke er tilgjengelig
                (kun aktuelt utenfor RPi).
        """
        if len(gpio_pins) != self.NUM_BUTTONS:
            raise ValueError(
                f"Krever {self.NUM_BUTTONS} GPIO-pinner, fikk {len(gpio_pins)}."
            )

        # gpiozero importeres lokalt for å unngå ImportError ved
        # kjøring på dev-PC der biblioteket ikke er installert.
        from gpiozero import Button

        self._buttons = [
            Button(pin, pull_up=True, bounce_time=None)
            for pin in gpio_pins
        ]

    def read(self) -> int:
        """Les nåværende knappestatus som bitmaske."""
        mask = 0
        for i, btn in enumerate(self._buttons):
            if btn.is_pressed:
                mask |= 1 << i
        return mask

    def close(self) -> None:
        """Frigjør GPIO-pinnene. Idempotent."""
        for btn in self._buttons:
            btn.close()
        self._buttons = []
