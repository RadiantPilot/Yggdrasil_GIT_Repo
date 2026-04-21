"""
formatting.py · Formateringshjelp for GUI-verdier.

Gir konsistente formateringsstrenger for millimeter, grader,
akselerasjon, vinkelhastighet og tid.
"""

from __future__ import annotations


def fmt_mm(v: float, decimals: int = 2) -> str:
    """Formater millimeter-verdi."""
    return f"{v:+.{decimals}f} mm"


def fmt_deg(v: float, decimals: int = 2) -> str:
    """Formater grader-verdi."""
    return f"{v:+.{decimals}f}°"


def fmt_accel(v: float) -> str:
    """Formater akselerasjon (m/s²)."""
    return f"{v:+.4f} m/s²"


def fmt_gyro(v: float) -> str:
    """Formater vinkelhastighet (°/s)."""
    return f"{v:+.4f} °/s"


def fmt_hz(v: float) -> str:
    """Formater frekvens."""
    return f"{v:.1f} Hz"


def fmt_time(seconds: float) -> str:
    """Formater sekunder til HH:MM:SS."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_val(v: float, decimals: int = 2) -> str:
    """Generell verdi-formatering."""
    return f"{v:.{decimals}f}"
