# theme.py
# ========
# Farger, fonter og visuelle konstanter for GUI-et.
# Definerer et konsistent morkt tema for hele applikasjonen.

from __future__ import annotations


# --- Fargepalett ---

# Bakgrunner
BG_PRIMARY = "#1a1a2e"      # Hovedvindu
BG_PANEL = "#16213e"         # Paneler og faner
BG_ACCENT = "#0f3460"        # Aktive elementer, knapper

# Tekst
TEXT_PRIMARY = "#e0e0e0"     # Hovedtekst
TEXT_SECONDARY = "#a0a0b0"   # Sekundaertekst, etiketter
TEXT_MUTED = "#707080"       # Dempet tekst

# Statusfarger
COLOR_OK = "#4CAF50"         # Gronn — trygg / kjoerer
COLOR_WARNING = "#FFC107"    # Gul — advarsel
COLOR_ERROR = "#F44336"      # Rod — feil / nodstopp
COLOR_EMERGENCY = "#D32F2F"  # Mork rod — nodstopp-knapp

# Aksenter
COLOR_CYAN = "#00BCD4"       # Tilt-markor (live-modus)
COLOR_BLUE = "#2196F3"       # Sliders, aktive elementer
COLOR_MARKER = "#FFC107"     # Tilt-kryss (visningsmodus)

# Tilt-sirkel
TILT_BG = "#1a1a2e"          # Sirkel-bakgrunn
TILT_RING = "#3a3a5a"        # Ytre ring
TILT_INNER_RING = "#2a2a4a"  # Indre ring (stiplet)
TILT_CROSSHAIR = "#404060"   # Sentrumskryss
TILT_MARKER_LIVE = COLOR_CYAN
TILT_MARKER_VIEW = COLOR_MARKER

# 3D-visning
COLOR_BASE_PLATE = "#808080"   # Gra bunnplate
COLOR_TOP_PLATE = "#4a90d9"    # Bla toppplate
COLOR_LEG_OK = "#4CAF50"       # Gronn bein
COLOR_LEG_WARN = "#FFC107"     # Gult bein (naer grense)
COLOR_LEG_DANGER = "#F44336"   # Rodt bein (over grense)

# --- Fonter ---
FONT_HEADER = ("Segoe UI", 16, "bold")
FONT_BODY = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_MONO = ("Consolas", 14)
FONT_MONO_LARGE = ("Consolas", 18)
FONT_EMERGENCY = ("Segoe UI", 16, "bold")

# --- Storrelse ---
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
TOP_BAR_HEIGHT = 50
SAFETY_BAR_HEIGHT = 55
IMU_PANEL_HEIGHT = 100
TILT_CIRCLE_RADIUS = 180

# --- Oppdateringsintervaller (ms) ---
GUI_UPDATE_INTERVAL_MS = 50    # 20 Hz for hovud-GUI
PLOT_3D_INTERVAL_MS = 100      # 10 Hz for matplotlib
