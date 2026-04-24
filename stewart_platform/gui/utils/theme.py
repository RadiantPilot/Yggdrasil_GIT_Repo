"""
theme.py · Lys/mørk tema for Yggdrasil GUI.

Holder fargepalett + global QSS for applikasjonen og broadcastet
en endring via ThemeManager slik at plot-widgets (pyqtgraph) kan
oppdatere bakgrunn, akser og rutenett når brukeren bytter tema.
"""

from __future__ import annotations

from dataclasses import dataclass

import pyqtgraph as pg
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Theme:
    """Fargepalett for ett tema."""
    name: str
    window_bg: str
    window_fg: str
    base_bg: str        # bakgrunn for input-felter
    alternate_bg: str   # tabell-stripes
    tooltip_bg: str
    tooltip_fg: str
    button_bg: str
    button_fg: str
    highlight: str
    highlight_fg: str
    border: str
    muted_fg: str       # sekundærtekst
    plot_bg: str
    plot_fg: str
    plot_axis: str
    grid_alpha: float


LIGHT = Theme(
    name="light",
    window_bg="#f5f5f5",
    window_fg="#1d1d1d",
    base_bg="#ffffff",
    alternate_bg="#ececec",
    tooltip_bg="#ffffe0",
    tooltip_fg="#000000",
    button_bg="#e6e6e6",
    button_fg="#1d1d1d",
    highlight="#3498db",
    highlight_fg="#ffffff",
    border="#c8c8c8",
    muted_fg="#6b6b6b",
    plot_bg="#ffffff",
    plot_fg="#222222",
    plot_axis="#444444",
    grid_alpha=0.25,
)

DARK = Theme(
    name="dark",
    window_bg="#232629",
    window_fg="#e6e6e6",
    base_bg="#2b2f33",
    alternate_bg="#2f3236",
    tooltip_bg="#3a3f44",
    tooltip_fg="#e6e6e6",
    button_bg="#3a3f44",
    button_fg="#e6e6e6",
    highlight="#3498db",
    highlight_fg="#ffffff",
    border="#4a4f54",
    muted_fg="#9aa0a6",
    plot_bg="#1e2124",
    plot_fg="#d6d6d6",
    plot_axis="#9aa0a6",
    grid_alpha=0.35,
)


def _build_palette(t: Theme) -> QPalette:
    """Bygg QPalette for gitt tema."""
    p = QPalette()
    p.setColor(QPalette.Window, QColor(t.window_bg))
    p.setColor(QPalette.WindowText, QColor(t.window_fg))
    p.setColor(QPalette.Base, QColor(t.base_bg))
    p.setColor(QPalette.AlternateBase, QColor(t.alternate_bg))
    p.setColor(QPalette.ToolTipBase, QColor(t.tooltip_bg))
    p.setColor(QPalette.ToolTipText, QColor(t.tooltip_fg))
    p.setColor(QPalette.Text, QColor(t.window_fg))
    p.setColor(QPalette.Button, QColor(t.button_bg))
    p.setColor(QPalette.ButtonText, QColor(t.button_fg))
    p.setColor(QPalette.Highlight, QColor(t.highlight))
    p.setColor(QPalette.HighlightedText, QColor(t.highlight_fg))
    p.setColor(QPalette.PlaceholderText, QColor(t.muted_fg))
    return p


def _build_stylesheet(t: Theme) -> str:
    """Globalt QSS som bakker opp paletten for widgets med egne stilark."""
    return f"""
        QMainWindow, QWidget {{ background: {t.window_bg}; color: {t.window_fg}; }}
        QToolBar {{ background: {t.window_bg}; border: 0; }}
        QStatusBar {{ background: {t.window_bg}; color: {t.muted_fg}; }}
        QGroupBox {{
            border: 1px solid {t.border};
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 6px;
            color: {t.window_fg};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }}
        QLabel {{ color: {t.window_fg}; background: transparent; }}
        QPushButton {{
            background: {t.button_bg};
            color: {t.button_fg};
            border: 1px solid {t.border};
            border-radius: 3px;
            padding: 4px 10px;
        }}
        QPushButton:hover {{ background: {t.alternate_bg}; }}
        QPushButton:disabled {{ color: {t.muted_fg}; }}
        QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit {{
            background: {t.base_bg};
            color: {t.window_fg};
            border: 1px solid {t.border};
            border-radius: 3px;
            padding: 2px 4px;
        }}
        QTableWidget {{
            background: {t.base_bg};
            color: {t.window_fg};
            gridline-color: {t.border};
            alternate-background-color: {t.alternate_bg};
        }}
        QHeaderView::section {{
            background: {t.alternate_bg};
            color: {t.window_fg};
            border: 1px solid {t.border};
            padding: 4px;
        }}
        QTabWidget::pane {{ border: 1px solid {t.border}; }}
        QTabBar::tab {{
            background: {t.alternate_bg};
            color: {t.window_fg};
            border: 1px solid {t.border};
            padding: 6px 14px;
        }}
        QTabBar::tab:selected {{
            background: {t.base_bg};
            border-bottom-color: {t.base_bg};
        }}
        QCheckBox {{ color: {t.window_fg}; }}
        QSlider::groove:horizontal {{
            background: {t.alternate_bg};
            height: 4px;
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {t.highlight};
            width: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
    """


class ThemeManager(QObject):
    """Global tema-styrer. Kun én instans opprettes av app.py."""

    theme_changed = Signal(object)  # emit Theme

    _instance: "ThemeManager | None" = None

    def __init__(self) -> None:
        super().__init__()
        self._current: Theme = LIGHT

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    @property
    def current(self) -> Theme:
        return self._current

    def apply(self, theme: Theme) -> None:
        """Påtving `theme` på QApplication og varsle abonnenter."""
        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")
            app.setPalette(_build_palette(theme))
            app.setStyleSheet(_build_stylesheet(theme))
        # Default for pyqtgraph-plot opprettet etter dette
        pg.setConfigOption("background", theme.plot_bg)
        pg.setConfigOption("foreground", theme.plot_fg)
        self._current = theme
        self.theme_changed.emit(theme)

    def toggle(self) -> Theme:
        """Bytt mellom lys og mørk — returner det nye temaet."""
        new = DARK if self._current is LIGHT else LIGHT
        self.apply(new)
        return new
