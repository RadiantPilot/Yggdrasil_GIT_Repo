"""
realtime_plot.py · Tunet pyqtgraph-wrapper for Pi 4B.

Hvis y_range er gitt brukes en fast Y-akse (raskest). Ellers skjer
manuell autorange kun hvert N-te tick — pyqtgraph sin innebygde
auto-range ville kostet en full datascan ved hver setData().

Tegning er throttlet til _RENDER_HZ via en QTimer; append_values
legger data inn i ringbufferen umiddelbart, men setData() skjer
sjelden og hopper helt over hvis widgeten er skjult.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer

from ..utils.ring_buffer import RingBuffer
from ..utils.theme import Theme, ThemeManager

# Maksimal tegnerate. 5 Hz holder grafen flytende for mennesker
# uten å overbelaste GUI-tråden på Pi 4B.
_RENDER_HZ = 2
_RENDER_INTERVAL_MS = int(1000 / _RENDER_HZ)

# Hvor ofte vi kjører manuell autorange når y_range ikke er gitt.
# 10 ticks × 200 ms = ca. 2 sek mellom omskaleringer — i praksis
# tilstrekkelig for sensordata som varierer i et begrenset område.
_AUTORANGE_EVERY_N = 10

_COLORS = ["#4a9a3c", "#3498db", "#e74c3c", "#f39c12", "#9b59b6", "#1abc9c"]


class RealtimePlot(pg.PlotWidget):
    """Sanntids rullerende plot.

    Args:
        series_names: Navn per serie (også brukt som legend).
        window_size: Antall samples i ringbufferen.
        y_label: Tekst på Y-aksen.
        y_range: Hvis satt, fast (min, max). Ellers manuell sjelden autorange.
        show_legend: Vis legend for >1 serie.
    """

    def __init__(
        self,
        series_names: list[str] | None = None,
        window_size: int = 150,
        y_label: str = "",
        y_range: tuple[float, float] | None = None,
        show_legend: bool = True,
        invert_x: bool = False,
    ) -> None:
        super().__init__()
        self._y_label = y_label
        self._y_range = y_range
        self._legend: pg.LegendItem | None = None

        # Brukerinteraksjon i grafen er deaktivert — kontekstmeny og
        # mus-zoom genererer overflødige paint-events.
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.hideButtons()

        if invert_x:
            self.getPlotItem().invertX(True)

        if y_range is not None:
            self.setYRange(*y_range, padding=0)
            self.enableAutoRange(axis="y", enable=False)
        else:
            # Vi kjører selv autorange i _do_refresh hvert N-te tick.
            self.enableAutoRange(axis="y", enable=False)

        names = series_names or ["y"]
        self._names = list(names)
        self._buffers: list[RingBuffer] = []
        self._curves: list[pg.PlotDataItem] = []
        self._visible: list[bool] = []

        for i, name in enumerate(names):
            buf = RingBuffer(window_size, 1)
            color = _COLORS[i % len(_COLORS)]
            curve = self.plot(pen=pg.mkPen(color=color, width=1.0), name=name)
            self._buffers.append(buf)
            self._curves.append(curve)
            self._visible.append(True)

        if show_legend and len(names) > 1:
            self._legend = self.addLegend(offset=(10, 10))

        mgr = ThemeManager.instance()
        self._apply_theme(mgr.current)
        mgr.theme_changed.connect(self._apply_theme)

        self._dirty = False
        self._render_tick = 0
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(_RENDER_INTERVAL_MS)
        self._render_timer.timeout.connect(self._do_refresh)
        self._render_timer.start()

    def _apply_theme(self, theme: Theme) -> None:
        self.setBackground(theme.plot_bg)
        self.showGrid(x=False, y=False)
        for ax_name in ("left", "bottom"):
            ax = self.getAxis(ax_name)
            ax.setPen(pg.mkPen(theme.plot_axis))
            ax.setTextPen(pg.mkPen(theme.plot_fg))
        if self._y_label:
            self.setLabel("left", self._y_label, color=theme.plot_fg)

    def append_values(self, values: list[float]) -> None:
        """Legg til en sample for alle serier."""
        for i, v in enumerate(values):
            if i < len(self._buffers):
                self._buffers[i].append(v)
        self._dirty = True

    def refresh(self) -> None:
        """Marker at data er endret. Faktisk tegning skjer via timer."""
        self._dirty = True

    def _do_refresh(self) -> None:
        """Tegn kurvene hvis det er nye data og widgeten er synlig."""
        if not self._dirty or not self.isVisible():
            return
        self._dirty = False
        self._render_tick += 1

        ymin = float("inf")
        ymax = float("-inf")
        do_autorange = self._y_range is None and (self._render_tick % _AUTORANGE_EVERY_N == 0)

        for i, (buf, curve) in enumerate(zip(self._buffers, self._curves)):
            if not self._visible[i]:
                curve.setData([])
                continue
            data = buf.get_channel(0)
            if len(data) == 0:
                continue
            # setData uten x-array er raskere — pyqtgraph genererer
            # implisitt arange. skipFiniteCheck dropper en valider-loop.
            curve.setData(data, skipFiniteCheck=True)
            if do_autorange:
                ymin = min(ymin, float(np.min(data)))
                ymax = max(ymax, float(np.max(data)))

        if do_autorange and ymin < ymax:
            margin = (ymax - ymin) * 0.1 or 0.5
            self.setYRange(ymin - margin, ymax + margin, padding=0)

    def clear_data(self) -> None:
        """Tøm all data."""
        for buf in self._buffers:
            buf.clear()
        self._dirty = True
        self._do_refresh()

    def set_series_visible(self, index: int, visible: bool) -> None:
        if 0 <= index < len(self._visible):
            self._visible[index] = visible
            self.refresh()

    def set_window_size(self, size: int) -> None:
        size = max(10, int(size))
        new_buffers: list[RingBuffer] = []
        for old in self._buffers:
            nb = RingBuffer(size, 1)
            data = old.get_channel(0)
            if len(data) > 0:
                for v in data[-size:]:
                    nb.append(float(v))
            new_buffers.append(nb)
        self._buffers = new_buffers
        self._dirty = True

    @property
    def series_names(self) -> list[str]:
        return list(self._names)
