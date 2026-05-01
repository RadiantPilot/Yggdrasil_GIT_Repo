# attiny_i2c_buttons.py
# =====================
# Konkret ButtonInterface-implementasjon som leser knappestatus
# fra ATTINY1624 over I2C. Firmwaren på ATTINY
# (firmware/knappekort.ino) poller selv pinnene, debouncer, og
# returnerer en byte med 5 bit-kodet trykkstatus når master
# gjør en read-request.

from __future__ import annotations

from typing import List

from .button_interface import ButtonInterface
from .i2c_bus import I2CBus


class AttinyI2CButtons(ButtonInterface):
    """Leser knappekortet via en ATTINY1624 på I2C-bussen.

    ATTINY-firmwaren leser selv knappepinnene og publiserer
    statusen som én byte på I2C. Hver bit i byten tilsvarer
    én knapp. Default-mappingen er bit 0 = knapp 1, …, bit 4
    = knapp 5, men den kan overstyres via button_bits hvis
    firmwaren legger ut bit-mønsteret i en annen rekkefølge.
    """

    def __init__(
        self,
        bus: I2CBus,
        address: int = 0x20,
        button_bits: List[int] | None = None,
    ) -> None:
        """Opprett driveren.

        Args:
            bus: Felles I2CBus-instans (deles med PCA9685 og IMU).
            address: I2C-adressen ATTINY-firmwaren responderer på.
            button_bits: Hvilken bit i den leste byten som tilsvarer
                hvilken knapp. Default [0, 1, 2, 3, 4] matcher
                firmware/knappekort.ino.

        Raises:
            ValueError: Hvis button_bits har feil lengde eller
                inneholder bit-indekser utenfor 0..7.
        """
        self._bus = bus
        self._address = address
        self._button_bits = button_bits or [0, 1, 2, 3, 4]

        if len(self._button_bits) != self.NUM_BUTTONS:
            raise ValueError(
                f"button_bits må ha {self.NUM_BUTTONS} elementer, "
                f"fikk {len(self._button_bits)}."
            )
        for bit in self._button_bits:
            if not 0 <= bit < 8:
                raise ValueError(
                    f"Bit-indeks må være 0..7, fikk {bit}."
                )

    def read(self) -> int:
        """Les knappestatus fra ATTINY og remap til standard bitmaske."""
        raw = self._bus.read_byte(self._address)
        mask = 0
        for i, bit in enumerate(self._button_bits):
            if raw & (1 << bit):
                mask |= 1 << i
        return mask

    def close(self) -> None:
        """ATTINY-driveren eier ikke bussen — ingenting å frigjøre."""
        return
