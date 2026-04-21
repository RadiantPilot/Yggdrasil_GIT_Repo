"""
gui · PySide6-basert GUI for Yggdrasil Stewart-plattform.

All kommunikasjon mot domene-koden (`stewart_platform`-pakkene) går
utelukkende gjennom `gui.bridge.controller_bridge.ControllerBridge` —
widgets skal aldri importere direkte fra control/, safety/ eller
hardware/.

Inngangspunkt:
    python -m stewart_platform.gui              # ekte hardware
    python -m stewart_platform.gui --mock       # simulert, uten Pi
"""
