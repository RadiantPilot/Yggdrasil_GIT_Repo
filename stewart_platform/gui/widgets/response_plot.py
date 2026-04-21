"""
response_plot.py · Step-respons-graf med metrikk-overlegg.

Viser setpunkt og faktisk verdi for en step-respons.
Beregner og viser overshoot, rise time, settle time og
steady-state error.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg


class ResponsePlot(pg.PlotWidget):
    """Step-respons graf for PID-tuning."""

    def __init__(self, y_label: str = "") -> None:
        super().__init__()
        self.setBackground("w")
        self.showGrid(x=True, y=True, alpha=0.3)
        if y_label:
            self.setLabel("left", y_label)
        self.setLabel("bottom", "tid (s)")

        self._setpoint_curve = self.plot(
            pen=pg.mkPen(color="#2ecc71", width=2, style=pg.QtCore.Qt.DashLine),
            name="Setpunkt",
        )
        self._actual_curve = self.plot(
            pen=pg.mkPen(color="#3498db", width=2),
            name="Faktisk",
        )
        self.addLegend(offset=(10, 10))

        # Metrikk-tekst
        self._metrics_text = pg.TextItem("", anchor=(0, 0))
        self._metrics_text.setPos(0, 0)
        self.addItem(self._metrics_text)

    def set_data(
        self,
        timestamps: np.ndarray,
        setpoints: np.ndarray,
        actuals: np.ndarray,
    ) -> None:
        """Oppdater plottet med step-respons-data.

        Args:
            timestamps: Tidspunkt for hver sample (sekunder).
            setpoints: Setpunkt-verdier.
            actuals: Faktiske målte verdier.
        """
        if len(timestamps) == 0:
            return
        t = timestamps - timestamps[0]
        self._setpoint_curve.setData(t, setpoints)
        self._actual_curve.setData(t, actuals)
        self._update_metrics(t, setpoints, actuals)

    def _update_metrics(
        self,
        t: np.ndarray,
        sp: np.ndarray,
        actual: np.ndarray,
    ) -> None:
        """Beregn og vis step-respons-metrikker."""
        if len(t) < 2 or len(sp) < 2:
            return

        target = sp[-1]
        start = actual[0]
        step_size = abs(target - start)

        if step_size < 1e-6:
            return

        # Overshoot
        if target > start:
            peak = np.max(actual)
            overshoot = max(0, (peak - target) / step_size * 100)
        else:
            peak = np.min(actual)
            overshoot = max(0, (target - peak) / step_size * 100)

        # Rise time (10% → 90%)
        thresh_lo = start + 0.1 * (target - start)
        thresh_hi = start + 0.9 * (target - start)
        rise_start = np.argmax(actual >= thresh_lo) if target > start else np.argmax(actual <= thresh_lo)
        rise_end = np.argmax(actual >= thresh_hi) if target > start else np.argmax(actual <= thresh_hi)
        rise_time = (t[rise_end] - t[rise_start]) * 1000 if rise_end > rise_start else 0

        # Settle time (innenfor 2% av endelig verdi)
        band = 0.02 * step_size
        settled = np.abs(actual - target) <= band
        if np.any(settled):
            last_outside = len(t) - 1 - np.argmax(settled[::-1])
            settle_time = t[min(last_outside + 1, len(t) - 1)] * 1000
        else:
            settle_time = t[-1] * 1000

        # Steady-state error
        ss_error = abs(actual[-1] - target)

        metrics = (
            f"OS: {overshoot:.1f}%  |  "
            f"Rise: {rise_time:.0f} ms  |  "
            f"Settle: {settle_time:.0f} ms  |  "
            f"SS err: {ss_error:.3f}"
        )
        self._metrics_text.setText(metrics)
        self._metrics_text.setPos(t[0], np.max(actual) * 1.05 if len(actual) > 0 else 0)

    def clear_data(self) -> None:
        """Tøm plottet."""
        self._setpoint_curve.setData([], [])
        self._actual_curve.setData([], [])
        self._metrics_text.setText("")
