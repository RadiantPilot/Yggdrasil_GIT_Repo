"""formatting.py · Formateringshjelpere for GUI-verdier."""

from __future__ import annotations


def fmt_deg(v: float, decimals: int = 2) -> str:
    """Formater grader-verdi."""
    return f"{v:+.{decimals}f}°"
