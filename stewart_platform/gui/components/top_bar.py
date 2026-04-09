# top_bar.py
# ==========
# Permanent toppbar med systemtilstand, start/stopp-knapper
# og tilgang til innstillinger.

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

import customtkinter as ctk

from .. import theme

if TYPE_CHECKING:
    from ..data_bridge import GUIDataBridge


class TopBar(ctk.CTkFrame):
    """Permanent toppbar — alltid synlig over fanene.

    Viser systemtilstand (KJOERER/STOPPET/NODSTOPP),
    start/stopp-knapper, og en knapp for a apne innstillinger.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        data_bridge: GUIDataBridge,
        on_settings: Optional[Callable[[], None]] = None,
        on_servo_menu: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent, fg_color=theme.BG_PANEL,
                         height=theme.TOP_BAR_HEIGHT, corner_radius=0)
        self.pack_propagate(False)

        self._data_bridge = data_bridge
        self._on_settings = on_settings
        self._on_servo_menu = on_servo_menu

        # --- Venstre: Tittel ---
        self._title = ctk.CTkLabel(
            self, text="Stewart Platform",
            font=("Segoe UI", 17, "bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self._title.pack(side="left", padx=(15, 20))

        # --- Status-indikator ---
        self._status_frame = ctk.CTkFrame(self, fg_color=theme.BG_ACCENT,
                                           corner_radius=6, height=30)
        self._status_frame.pack(side="left", padx=5)
        self._status_label = ctk.CTkLabel(
            self._status_frame, text=" STOPPET ",
            font=theme.FONT_BODY,
            text_color=theme.COLOR_WARNING,
        )
        self._status_label.pack(padx=10, pady=3)

        # --- Midten: Start/Stopp-knapper ---
        self._btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_frame.pack(side="left", padx=20)

        self._start_btn = ctk.CTkButton(
            self._btn_frame, text="Start", width=80, height=32,
            font=theme.FONT_BODY,
            fg_color=theme.COLOR_OK,
            hover_color="#388E3C",
            command=self._on_start,
        )
        self._start_btn.pack(side="left", padx=3)

        self._stop_btn = ctk.CTkButton(
            self._btn_frame, text="Stopp", width=80, height=32,
            font=theme.FONT_BODY,
            fg_color=theme.COLOR_ERROR,
            hover_color="#C62828",
            command=self._on_stop,
        )
        self._stop_btn.pack(side="left", padx=3)

        # --- Hoyre: Menyknapper ---
        self._settings_btn = ctk.CTkButton(
            self, text="Innstillinger",
            width=110, height=32,
            font=theme.FONT_SMALL,
            fg_color=theme.BG_ACCENT,
            hover_color=theme.COLOR_BLUE,
            command=self._open_settings,
        )
        self._settings_btn.pack(side="right", padx=(3, 15))

        self._servo_btn = ctk.CTkButton(
            self, text="Servoer",
            width=90, height=32,
            font=theme.FONT_SMALL,
            fg_color=theme.BG_ACCENT,
            hover_color=theme.COLOR_BLUE,
            command=self._open_servo_menu,
        )
        self._servo_btn.pack(side="right", padx=3)

    def _on_start(self) -> None:
        self._data_bridge.start()

    def _on_stop(self) -> None:
        self._data_bridge.stop()

    def _open_settings(self) -> None:
        if self._on_settings:
            self._on_settings()

    def _open_servo_menu(self) -> None:
        if self._on_servo_menu:
            self._on_servo_menu()

    def update_from_state(self) -> None:
        """Oppdater statusvisning fra data bridge."""
        state = self._data_bridge.get_state()

        if state.is_emergency_stopped:
            self._status_label.configure(
                text=" NODSTOPP ",
                text_color=theme.COLOR_ERROR,
            )
            self._status_frame.configure(fg_color="#3a0000")
        elif state.is_running:
            self._status_label.configure(
                text=" KJOERER ",
                text_color=theme.COLOR_OK,
            )
            self._status_frame.configure(fg_color=theme.BG_ACCENT)
        else:
            self._status_label.configure(
                text=" STOPPET ",
                text_color=theme.COLOR_WARNING,
            )
            self._status_frame.configure(fg_color=theme.BG_ACCENT)
