"""
ring_buffer.py · Numpy-basert rullerende vindu for sanntidsgrafer.

Holder de N siste verdiene for et vilkårlig antall serier.
Effektiv for pyqtgraph som krever numpy-arrays for rask tegning.
"""

from __future__ import annotations

import numpy as np


class RingBuffer:
    """Rullerende buffer med fast størrelse.

    Nye verdier skrives til neste posisjon og overskriver
    de eldste når bufferen er full. get_data() returnerer
    verdiene i kronologisk rekkefølge.
    """

    def __init__(self, capacity: int, channels: int = 1) -> None:
        """Opprett en ny ringbuffer.

        Args:
            capacity: Maks antall samples (vindusstørrelse).
            channels: Antall parallelle serier.
        """
        self._capacity = capacity
        self._data = np.zeros((capacity, channels), dtype=np.float64)
        self._index = 0
        self._count = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def count(self) -> int:
        """Antall samples skrevet (maks = capacity)."""
        return min(self._count, self._capacity)

    def append(self, values: np.ndarray | list[float] | float) -> None:
        """Legg til én sample (alle kanaler).

        Args:
            values: Verdi(er) for alle kanaler. Skalarverdier
                    er lov når channels=1.
        """
        arr = np.atleast_1d(np.asarray(values, dtype=np.float64))
        self._data[self._index % self._capacity] = arr
        self._index += 1
        self._count += 1

    def get_data(self) -> np.ndarray:
        """Hent data i kronologisk rekkefølge.

        Returns:
            Array med shape (count, channels), eldste først.
        """
        n = self.count
        if n < self._capacity:
            return self._data[:n].copy()
        start = self._index % self._capacity
        return np.roll(self._data, -start, axis=0).copy()

    def get_channel(self, ch: int) -> np.ndarray:
        """Hent én kanal som 1D-array."""
        return self.get_data()[:, ch]

    def clear(self) -> None:
        """Nullstill bufferen."""
        self._data[:] = 0.0
        self._index = 0
        self._count = 0
