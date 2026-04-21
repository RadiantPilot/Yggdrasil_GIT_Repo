# safety_bar.py
# =============
# Permanent sikkerhetsbar nederst med NODSTOPP-knapp,
# sikkerhetsstatus og tilbakestillingsknapp.

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from .. import theme

if TYPE_CHECKING:
    from ..data_bridge import GUIDataBridge


class SafetyBar(ctk.CTkFrame):
    """Permanent sikkerhetsbar — alltid synlig nederst.

    Inneholder:
    - Stor NODSTOPP-knapp (ingen bekreftelse)
    - Sikkerhetsstatus-indikator
    - Siste sikkerhetsbrudd
    - Tilbakestill nodstopp-knapp
    """

    def __init__(self, parent: ctk.CTkFrame, data_bridge: GUIDataBridge) -> None:
        super().__init__(parent, fg_color=theme.BG_PANEL,
                         height=theme.SAFETY_BAR_HEIGHT, corner_radius=0)
        self.pack_propagate(False)

        self._data_bridge = data_bridge

        # --- NODSTOPP-knapp ---
        self._estop_btn = ctk.CTkButton(
            self,
            text="NODSTOPP",
            width=140,
            height=42,
            font=theme.FONT_EMERGENCY,
            fg_color=theme.COLOR_EMERGENCY,
            hover_color="#B71C1C",
            text_color="white",
            corner_radius=6,
            command=self._on_emergency_stop,
        )
        self._estop_btn.pack(side="left", padx=(15, 10), pady=6)

        # --- Statusindikator ---
        self._status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._status_frame.pack(side="left", padx=10)

        ctk.CTkLabel(
            self._status_frame, text="Status:",
            font=theme.FONT_BODY,
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 5))

        self._status_dot = ctk.CTkLabel(
            self._status_frame, text="\u25cf",
            font=("Segoe UI", 16),
            text_color=theme.COLOR_OK,
        )
        self._status_dot.pack(side="left")

        self._status_text = ctk.CTkLabel(
            self._status_frame, text="OK",
            font=theme.FONT_BODY,
            text_color=theme.COLOR_OK,
        )
        self._status_text.pack(side="left", padx=(3, 0))

        # --- Bruddtekst ---
        self._violation_label = ctk.CTkLabel(
            self, text="",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_WARNING,
            anchor="w",
        )
        self._violation_label.pack(side="left", padx=20, fill="x", expand=True)

        # --- Tilbakestill-knapp ---
        self._reset_btn = ctk.CTkButton(
            self,
            text="Tilbakestill",
            width=110,
            height=32,
            font=theme.FONT_BODY,
            fg_color=theme.BG_ACCENT,
            hover_color=theme.COLOR_BLUE,
            state="disabled",
            command=self._on_reset,
        )
        self._reset_btn.pack(side="right", padx=(10, 15), pady=6)

    def _on_emergency_stop(self) -> None:
        """Utlos nodstopp umiddelbart."""
        self._data_bridge.emergency_stop()

    def _on_reset(self) -> None:
        """Tilbakestill nodstopp."""
        self._data_bridge.reset_latched_faults()

    def update_from_state(self) -> None:
        """Oppdater sikkerhetsstatus fra data bridge."""
        state = self._data_bridge.get_state()

        if state.is_e_stopped:
            self._status_dot.configure(text_color=theme.COLOR_ERROR)
            self._status_text.configure(
                text="NODSTOPP", text_color=theme.COLOR_ERROR)
            self._reset_btn.configure(state="normal")
        elif not state.safety_result.is_safe:
            self._status_dot.configure(text_color=theme.COLOR_WARNING)
            self._status_text.configure(
                text="ADVARSEL", text_color=theme.COLOR_WARNING)
            self._reset_btn.configure(state="disabled")
        else:
            self._status_dot.configure(text_color=theme.COLOR_OK)
            self._status_text.configure(
                text="OK", text_color=theme.COLOR_OK)
            self._reset_btn.configure(state="disabled")

        # Vis sikkerhetsbrudd
        violations = state.safety_result.violations
        if violations:
            self._violation_label.configure(text=" | ".join(violations))
        else:
            self._violation_label.configure(text="")
