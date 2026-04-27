"""
navigable.py · Protokoll for widgets som kan styres av knappekortet.

En Navigable er en widget som FocusManager kan rute knappetrykk til
i edit-mode. Protokollen bruker runtime-checkable Protocol for at
typesjekkere skal kunne verifisere at konkrete widgets oppfyller
kontrakten, og at FocusManager kan kalle metodene direkte uten
arvkjede.

Visuell tilstand styres via Qt-properties som theme-stylesheet'en
plukker opp:

  navState = ""        — ingen ramme
  navState = "focused" — tynn farget ramme (i nav-mode)
  navState = "edit"    — tykkere kontrastfarget ramme (i edit-mode)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PySide6.QtWidgets import QWidget


@runtime_checkable
class Navigable(Protocol):
    """Kontrakt for widgets som FocusManager kan styre."""

    def set_focused(self, focused: bool) -> None:
        """Tegnet eller fjern den lette fokus-ringen."""
        ...

    def set_edit_mode(self, edit: bool) -> None:
        """Tegnet eller fjern den tykkere edit-ringen."""
        ...

    def nav_horizontal(self, delta: int) -> None:
        """Venstre (delta=-1) eller høyre (delta=+1) i edit-mode.

        Implementasjonen bestemmer selv hva dette betyr — typisk
        å justere en verdi opp/ned med ett steg.
        """
        ...

    def nav_vertical(self, delta: int) -> None:
        """Opp (delta=-1) eller ned (delta=+1) i edit-mode.

        Implementasjonen bestemmer selv hva dette betyr — typisk
        å bla mellom delparametere innenfor widgeten.
        """
        ...


def apply_nav_state(widget: QWidget, state: str) -> None:
    """Sett navState-property og force re-styling.

    Theme-stylesheet'en har selectors `[navState="focused"]` og
    `[navState="edit"]` som tegner ramme. Qt cacher stylesheet-
    matching, så vi må kalle polish() for at endringen skal vises.

    Args:
        widget: Widgeten som skal endre tilstand.
        state: "", "focused" eller "edit".
    """
    widget.setProperty("navState", state)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()
