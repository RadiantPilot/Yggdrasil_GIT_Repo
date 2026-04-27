"""
focus_manager.py · Kjernen i det modale knappenavigasjonssystemet.

FocusManager mottar knappehendelser fra ButtonWorker og dispatcher
dem basert på modus:

  Nav-mode (default):
    venstre/høyre  → bytt tab
    opp/ned        → bytt fokusert widget i tab
    midt           → enter edit-mode
    lang-trykk midt → E-STOP

  Edit-mode:
    venstre/høyre  → fokusert widget.nav_horizontal(±1)
    opp/ned        → fokusert widget.nav_vertical(±1)
    midt           → tilbake til nav-mode
    lang-trykk midt → E-STOP

Knappeindeksering følger ButtonInterface: 0..4 = knapp 1..5.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QTabWidget

from .navigable import Navigable, apply_nav_state


class ButtonId(IntEnum):
    """Logiske navn på de 5 knappene."""

    LEFT = 0
    UP = 1
    CENTER = 2
    DOWN = 3
    RIGHT = 4


class FocusManager(QObject):
    """Holder navigasjonstilstand og ruter knappetrykk til widgets.

    Liv-syklus:
      1. Opprettes med referanser til QTabWidget og en E-STOP-callback.
      2. Hver tab kaller register_navigables() når dens widgets er
         opprettet, vanligvis via en get_navigables()-metode.
      3. Koble button_pressed/button_long_pressed-signaler fra
         ButtonWorker til on_pressed/on_long_pressed.
    """

    def __init__(
        self,
        tabs: QTabWidget,
        estop_callback: Callable[[], None],
    ) -> None:
        """Opprett manageren.

        Args:
            tabs: QTabWidget som inneholder alle hovedfanene.
            estop_callback: Funksjon som utløser E-STOP. Kalles ved
                lang-trykk på midt-knappen.
        """
        super().__init__()
        self._tabs = tabs
        self._estop_callback = estop_callback

        # En liste over Navigables per tab-indeks.
        self._navigables_per_tab: dict[int, List[Navigable]] = {}

        # Nåværende fokus-indeks innenfor aktiv tab. -1 = ingen.
        self._focused_index: int = -1
        self._edit_mode: bool = False

        self._tabs.currentChanged.connect(self._on_tab_changed)

    # ------------------------------------------------------------------
    # Registrering
    # ------------------------------------------------------------------

    def register_navigables(self, tab_index: int, items: List[Navigable]) -> None:
        """Sett listen over fokuserbare widgets for en bestemt tab.

        Kan kalles flere ganger — siste anrop vinner. Hvis tab-en
        er aktiv akkurat nå, oppdateres fokusring umiddelbart.
        """
        # Fjern eventuelle gamle fokusringer
        for w in self._navigables_per_tab.get(tab_index, []):
            self._set_state(w, "")

        self._navigables_per_tab[tab_index] = items

        if tab_index == self._tabs.currentIndex():
            self._reset_focus_for_active_tab()

    # ------------------------------------------------------------------
    # Knappehåndtering
    # ------------------------------------------------------------------

    @Slot(int)
    def on_pressed(self, button: int) -> None:
        """Slot som ButtonWorker.button_pressed kobles til."""
        if button == ButtonId.CENTER:
            self._toggle_edit_mode()
        elif self._edit_mode:
            self._dispatch_edit(button)
        else:
            self._dispatch_nav(button)

    @Slot(int)
    def on_long_pressed(self, button: int) -> None:
        """Slot som ButtonWorker.button_long_pressed kobles til."""
        if button == ButtonId.CENTER:
            self._estop_callback()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _dispatch_nav(self, button: int) -> None:
        """Knappetrykk i nav-mode (ikke midt — det håndteres separat)."""
        if button == ButtonId.LEFT:
            self._step_tab(-1)
        elif button == ButtonId.RIGHT:
            self._step_tab(+1)
        elif button == ButtonId.UP:
            self._step_focus(-1)
        elif button == ButtonId.DOWN:
            self._step_focus(+1)

    def _dispatch_edit(self, button: int) -> None:
        """Knappetrykk i edit-mode — delegeres til fokusert widget."""
        widget = self._current_widget()
        if widget is None:
            return
        if button == ButtonId.LEFT:
            widget.nav_horizontal(-1)
        elif button == ButtonId.RIGHT:
            widget.nav_horizontal(+1)
        elif button == ButtonId.UP:
            widget.nav_vertical(-1)
        elif button == ButtonId.DOWN:
            widget.nav_vertical(+1)

    def _toggle_edit_mode(self) -> None:
        """Veksle mellom nav- og edit-mode for fokusert widget."""
        widget = self._current_widget()
        if widget is None:
            # Ingenting å gå inn på — bli i nav-mode
            return

        self._edit_mode = not self._edit_mode
        widget.set_edit_mode(self._edit_mode)
        # I edit-mode er focus-ring redundant; sett bare én tilstand.
        if self._edit_mode:
            self._set_state(widget, "edit")
        else:
            self._set_state(widget, "focused")

    def _step_tab(self, delta: int) -> None:
        """Bytt aktiv tab med delta (-1 eller +1)."""
        n = self._tabs.count()
        if n == 0:
            return
        new_idx = (self._tabs.currentIndex() + delta) % n
        self._tabs.setCurrentIndex(new_idx)
        # _on_tab_changed tar seg av å oppdatere fokus

    def _step_focus(self, delta: int) -> None:
        """Bytt fokusert widget innen aktiv tab."""
        items = self._current_navigables()
        if not items:
            return

        prev = self._focused_index
        n = len(items)
        new_idx = (prev + delta) % n if prev >= 0 else 0

        if 0 <= prev < n:
            self._set_state(items[prev], "")
        self._focused_index = new_idx
        self._set_state(items[new_idx], "focused")

    @Slot(int)
    def _on_tab_changed(self, _index: int) -> None:
        """Bytt tab — gå tilbake til nav-mode og fokuser første widget."""
        # Forlat eventuelt edit-mode for forrige tab
        self._edit_mode = False
        self._reset_focus_for_active_tab()

    def _reset_focus_for_active_tab(self) -> None:
        """Sett fokus på første widget i aktiv tab (eller ingen)."""
        # Fjern fokusringer fra alle widgets i alle tabs (billig)
        for items in self._navigables_per_tab.values():
            for w in items:
                self._set_state(w, "")

        items = self._current_navigables()
        if items:
            self._focused_index = 0
            self._set_state(items[0], "focused")
        else:
            self._focused_index = -1

    def _current_navigables(self) -> List[Navigable]:
        """Returner navigables for aktiv tab, eller tom liste."""
        return self._navigables_per_tab.get(self._tabs.currentIndex(), [])

    def _current_widget(self) -> Optional[Navigable]:
        """Hent fokusert widget, eller None hvis ingen er fokusert."""
        items = self._current_navigables()
        if 0 <= self._focused_index < len(items):
            return items[self._focused_index]
        return None

    @staticmethod
    def _set_state(widget: Navigable, state: str) -> None:
        """Be widgeten oppdatere visuell tilstand.

        Bruker både den semantiske API-en (set_focused/set_edit_mode)
        og den generiske property-mekanismen, slik at widgets kan
        velge hvilket nivå de vil reagere på.
        """
        widget.set_focused(state == "focused")
        widget.set_edit_mode(state == "edit")
        # apply_nav_state forventer QWidget. Vår protokoll garanterer
        # ikke dette, men i praksis er alle Navigables QWidgets.
        try:
            apply_nav_state(widget, state)  # type: ignore[arg-type]
        except (AttributeError, TypeError):
            pass
