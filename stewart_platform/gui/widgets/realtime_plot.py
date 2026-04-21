"""
realtime_plot.py · Wrapper rundt pyqtgraph med rullerende vindu.

Gir en enkel interface for sanntidsplott med flere serier,
autoskalering og konfigurerbar vinduslengde.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from ..utils.ring_buffer import RingBuffer

# Farger for opptil 6 serier
_COLORS = ["#4a9a3c", "#3498db", "#e74c3c", "#f39c12", "#9b59b6", "#1abc9c"]


class RealtimePlot(pg.PlotWidget):
    """Sanntids rullerende plot basert på pyqtgraph.

    Holder en ringbuffer per serie og tegner de N siste
    samplesene på hver oppdatering.
    """

    def __init__(
        self,
        series_names: list[str] | None = None,
        window_size: int = 150,
        y_label: str = "",
        show_legend: bool = True,
    ) -> None:
        super().__init__()
        self.setBackground("w")
        self.showGrid(x=True, y=True, alpha=0.3)
        if y_label:
            self.setLabel("left", y_label)

        names = series_names or ["y"]
        self._buffers: list[RingBuffer] = []
        self._curves: list[pg.PlotDataItem] = []

        for i, name in enumerate(names):
            buf = RingBuffer(window_size, 1)
            color = _COLORS[i % len(_COLORS)]
            curve = self.plot(pen=pg.mkPen(color=color, width=1.5), name=name)
            self._buffers.append(buf)
            self._curves.append(curve)

        if show_legend and len(names) > 1:
            self.addLegend(offset=(10, 10))

    def append_values(self, values: list[float]) -> None:
        """Legg til en sample for alle serier.

        Args:
            values: Én verdi per serie. Lengden må matche antall serier.
        """
        for i, v in enumerate(values):
            if i < len(self._buffers):
                self._buffers[i].append(v)

    def refresh(self) -> None:
        """Oppdater kurvene fra bufferdata. Kall etter append_values."""
        for i, (buf, curve) in enumerate(zip(self._buffers, self._curves)):
            data = buf.get_channel(0)
            if len(data) > 0:
                curve.setData(np.arange(len(data)), data)

    def clear_data(self) -> None:
        """Tøm all data."""
        for buf in self._buffers:
            buf.clear()
        self.refresh()
