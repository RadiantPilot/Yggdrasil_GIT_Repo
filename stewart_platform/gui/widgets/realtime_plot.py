"""
realtime_plot.py · Wrapper rundt pyqtgraph med rullerende vindu.

Gir en enkel interface for sanntidsplott med flere serier og
konfigurerbar vinduslengde. Y-aksen auto-skaleres alltid; brukeren
kan kun zoome/panorere langs x-aksen for å bestemme hvor mye data
som vises om gangen. Lytter på ThemeManager for å oppdatere farger
når brukeren bytter lys/mørk modus.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer

from ..utils.ring_buffer import RingBuffer
from ..utils.theme import Theme, ThemeManager

# Maksimal visuell oppdateringsfrekvens i Hz. Pyqtgraph setData()
# kan ta 30-100 ms per kall på Raspberry Pi 4B med flere grafer
# samtidig — uten throttle blir GUI-tråden overbelastet og hele
# applikasjonen oppfattes som "frosset". 5 Hz er flytende nok for
# operatørens øye, og data legges fortsatt inn i ringbufferen ved
# full snapshot-rate slik at tegningen er sannferdig når den skjer.
_RENDER_HZ = 5
_RENDER_INTERVAL_MS = int(1000 / _RENDER_HZ)

# Farger for opptil 6 serier (samme for begge tema)
_COLORS = ["#4a9a3c", "#3498db", "#e74c3c", "#f39c12", "#9b59b6", "#1abc9c"]


class RealtimePlot(pg.PlotWidget):
    """Sanntids rullerende plot basert på pyqtgraph.

    Holder en ringbuffer per serie og tegner de N siste
    samplesene på hver oppdatering. Hver serie kan skjules
    individuelt via `set_series_visible`.
    """

    def __init__(
        self,
        series_names: list[str] | None = None,
        window_size: int = 150,
        y_label: str = "",
        show_legend: bool = True,
        lock_y: bool = True,
    ) -> None:
        super().__init__()
        self._y_label = y_label
        self._lock_y = lock_y
        self._legend: pg.LegendItem | None = None
        self._show_legend = show_legend

        # Begrens brukerens zoom-frihet
        if lock_y:
            # Brukeren kan kun zoome/panorere langs x; y følger data.
            self.setMouseEnabled(x=True, y=False)
            self.enableAutoRange(axis="y", enable=True)
            self.setMenuEnabled(False)

        names = series_names or ["y"]
        self._names = list(names)
        self._buffers: list[RingBuffer] = []
        self._curves: list[pg.PlotDataItem] = []
        self._visible: list[bool] = []

        for i, name in enumerate(names):
            buf = RingBuffer(window_size, 1)
            color = _COLORS[i % len(_COLORS)]
            curve = self.plot(pen=pg.mkPen(color=color, width=1.5), name=name)
            self._buffers.append(buf)
            self._curves.append(curve)
            self._visible.append(True)

        if show_legend and len(names) > 1:
            self._legend = self.addLegend(offset=(10, 10))

        # Lytt på tema-endringer og anvend gjeldende tema én gang
        mgr = ThemeManager.instance()
        self._apply_theme(mgr.current)
        mgr.theme_changed.connect(self._apply_theme)

        # Throttle-rendering: append_values legger inn data straks,
        # men selve setData()-tegningen skjer kun ved jevne tick fra
        # denne timeren — slik at GUI-tråden ikke overbelastes når
        # snapshots kommer raskere enn pyqtgraph rekker å tegne.
        self._dirty = False
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(_RENDER_INTERVAL_MS)
        self._render_timer.timeout.connect(self._do_refresh)
        self._render_timer.start()

    # ------------------------------------------------------------------
    # Tema
    # ------------------------------------------------------------------

    def _apply_theme(self, theme: Theme) -> None:
        """Oppdater bakgrunn, akser og grid til gitt tema."""
        self.setBackground(theme.plot_bg)
        self.showGrid(x=True, y=True, alpha=theme.grid_alpha)
        for ax_name in ("left", "bottom"):
            ax = self.getAxis(ax_name)
            ax.setPen(pg.mkPen(theme.plot_axis))
            ax.setTextPen(pg.mkPen(theme.plot_fg))
        if self._y_label:
            self.setLabel("left", self._y_label, color=theme.plot_fg)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def append_values(self, values: list[float]) -> None:
        """Legg til en sample for alle serier.

        Args:
            values: Én verdi per serie. Lengden må matche antall serier.
        """
        for i, v in enumerate(values):
            if i < len(self._buffers):
                self._buffers[i].append(v)
        self._dirty = True

    def refresh(self) -> None:
        """Marker at data er endret — selve tegningen skjer via timer.

        Beholdt som offentlig API for bakoverkompatibilitet med
        kallende kode (imu_tab, pid_tuning_tab) som forventer å kunne
        be om en oppdatering. Vi setter bare dirty-flagget her; den
        faktiske setData() utføres av _do_refresh ved neste tick.
        """
        self._dirty = True

    def _do_refresh(self) -> None:
        """Tegn kurvene hvis det er nye data siden forrige tick."""
        if not self._dirty:
            return
        self._dirty = False
        for i, (buf, curve) in enumerate(zip(self._buffers, self._curves)):
            if not self._visible[i]:
                curve.setData([], [])
                continue
            data = buf.get_channel(0)
            if len(data) > 0:
                curve.setData(np.arange(len(data)), data)

    def clear_data(self) -> None:
        """Tøm all data."""
        for buf in self._buffers:
            buf.clear()
        # Tving en umiddelbar tegning slik at den blanke tilstanden
        # vises uten å vente på neste timer-tick.
        self._dirty = True
        self._do_refresh()

    # ------------------------------------------------------------------
    # Kontroll
    # ------------------------------------------------------------------

    def set_series_visible(self, index: int, visible: bool) -> None:
        """Skjul eller vis én serie uten å miste bufferdata."""
        if 0 <= index < len(self._visible):
            self._visible[index] = visible
            self.refresh()

    def set_window_size(self, size: int) -> None:
        """Endre vinduslengden (antall samples vist)."""
        size = max(10, int(size))
        new_buffers: list[RingBuffer] = []
        for old in self._buffers:
            nb = RingBuffer(size, 1)
            # Bevar de siste `size` samples ved bytte
            data = old.get_channel(0)
            if len(data) > 0:
                for v in data[-size:]:
                    nb.append(float(v))
            new_buffers.append(nb)
        self._buffers = new_buffers
        self.refresh()

    @property
    def series_names(self) -> list[str]:
        return list(self._names)
