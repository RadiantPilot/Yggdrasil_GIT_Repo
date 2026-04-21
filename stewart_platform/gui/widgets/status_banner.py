"""
status_banner.py · Stor statusbanner for overview og safety tabs.

Viser en farget banner med status-ikon, tittel og undertekst.
Farger: grønn (kjører), gul (advarsel), rød (e-stop), grå (stoppet).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

_STYLES = {
    "running": ("background: rgba(74,154,60,0.15); border: 1px solid rgba(74,154,60,0.3);", "●", "color: #4a9a3c;"),
    "stopped": ("background: rgba(160,160,160,0.10); border: 1px solid rgba(160,160,160,0.3);", "■", "color: #888;"),
    "warning": ("background: rgba(212,160,23,0.12); border: 1px solid rgba(212,160,23,0.3);", "▲", "color: #d4a017;"),
    "error": ("background: rgba(197,52,52,0.12); border: 1px solid rgba(197,52,52,0.3);", "⬤", "color: #c53434;"),
}


class StatusBanner(QWidget):
    """Stor statusbanner med ikon, tittel og undertekst."""

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        self._icon = QLabel("●")
        self._icon.setStyleSheet("font-size: 18px;")
        layout.addWidget(self._icon)

        text_col = QWidget()
        tcl = QHBoxLayout(text_col)
        tcl.setContentsMargins(0, 0, 0, 0)
        tcl.setSpacing(16)

        self._title = QLabel("System")
        self._title.setStyleSheet("font-size: 18px; font-weight: 600;")
        tcl.addWidget(self._title)

        self._subtitle = QLabel("")
        self._subtitle.setStyleSheet("font-size: 11px; color: #666;")
        tcl.addWidget(self._subtitle)
        tcl.addStretch()

        layout.addWidget(text_col, 1)

        self.setStyleSheet("border-radius: 4px;")
        self.set_status("stopped", "System stoppet", "")

    def set_status(self, status: str, title: str, subtitle: str) -> None:
        """Oppdater banneret.

        Args:
            status: 'running', 'stopped', 'warning', 'error'
            title: Hovedtekst.
            subtitle: Undertekst.
        """
        bg, icon, color = _STYLES.get(status, _STYLES["stopped"])
        self.setStyleSheet(f"QWidget {{ {bg} border-radius: 4px; }}")
        self._icon.setText(icon)
        self._icon.setStyleSheet(f"font-size: 18px; {color}")
        self._title.setText(title)
        self._title.setStyleSheet(f"font-size: 18px; font-weight: 600; {color}")
        self._subtitle.setText(subtitle)
