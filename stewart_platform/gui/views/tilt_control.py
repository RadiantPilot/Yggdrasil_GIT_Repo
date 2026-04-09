# tilt_control.py
# ===============
# Fane 1: Interaktiv tilt-styring.
# Inneholder tilt-sirkelen med modusbytte og roll/pitch-avlesning.

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from .. import theme
from ..widgets.tilt_circle import TiltCircle

if TYPE_CHECKING:
    from ..data_bridge import GUIDataBridge


class TiltControlView(ctk.CTkFrame):
    """Fane for interaktiv tilt-styring av plattformen.

    Inneholder:
    - Stor tilt-sirkel for roll/pitch-styring
    - Toggle mellom live- og visningsmodus
    - Numerisk avlesning av roll og pitch
    - Tilbakestill-knapp
    """

    def __init__(self, parent: ctk.CTkFrame, data_bridge: GUIDataBridge) -> None:
        super().__init__(parent, fg_color="transparent")
        self._data_bridge = data_bridge

        # --- Hovedinnhold ---
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(expand=True, fill="both", padx=10, pady=10)

        # Venstre: Tilt-sirkel
        self._circle_frame = ctk.CTkFrame(self._content, fg_color=theme.BG_PANEL,
                                           corner_radius=10)
        self._circle_frame.pack(side="left", expand=True, fill="both", padx=(0, 5))

        # Tittel
        ctk.CTkLabel(
            self._circle_frame,
            text="Tilt-styring",
            font=theme.FONT_HEADER,
            text_color=theme.TEXT_PRIMARY,
        ).pack(pady=(15, 5))

        # Tilt-sirkel widget
        self._tilt_circle = TiltCircle(
            self._circle_frame,
            max_angle=30.0,
            on_tilt_change=self._on_tilt_change,
        )
        self._tilt_circle.pack(pady=10)

        # --- Kontrollpanel (hoyre) ---
        self._control_frame = ctk.CTkFrame(self._content, fg_color=theme.BG_PANEL,
                                            corner_radius=10, width=220)
        self._control_frame.pack(side="right", fill="y", padx=(5, 0))
        self._control_frame.pack_propagate(False)

        # Modus-toggle
        ctk.CTkLabel(
            self._control_frame,
            text="Modus",
            font=theme.FONT_BODY,
            text_color=theme.TEXT_SECONDARY,
        ).pack(pady=(20, 5))

        self._mode_var = ctk.StringVar(value="Live")
        self._mode_toggle = ctk.CTkSegmentedButton(
            self._control_frame,
            values=["Live", "Visning"],
            variable=self._mode_var,
            command=self._on_mode_change,
            font=theme.FONT_BODY,
        )
        self._mode_toggle.pack(padx=15, pady=5)

        # Separator
        ctk.CTkFrame(self._control_frame, height=2,
                      fg_color=theme.TILT_CROSSHAIR).pack(fill="x", padx=15, pady=15)

        # Avlesninger
        ctk.CTkLabel(
            self._control_frame,
            text="Verdier",
            font=theme.FONT_BODY,
            text_color=theme.TEXT_SECONDARY,
        ).pack(pady=(0, 5))

        # Roll
        self._roll_frame = ctk.CTkFrame(self._control_frame, fg_color="transparent")
        self._roll_frame.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(self._roll_frame, text="Roll:",
                      font=theme.FONT_BODY, text_color=theme.TEXT_SECONDARY,
                      width=60, anchor="w").pack(side="left")
        self._roll_label = ctk.CTkLabel(
            self._roll_frame, text="0.0\u00b0",
            font=theme.FONT_MONO_LARGE, text_color=theme.COLOR_CYAN,
        )
        self._roll_label.pack(side="right")

        # Pitch
        self._pitch_frame = ctk.CTkFrame(self._control_frame, fg_color="transparent")
        self._pitch_frame.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(self._pitch_frame, text="Pitch:",
                      font=theme.FONT_BODY, text_color=theme.TEXT_SECONDARY,
                      width=60, anchor="w").pack(side="left")
        self._pitch_label = ctk.CTkLabel(
            self._pitch_frame, text="0.0\u00b0",
            font=theme.FONT_MONO_LARGE, text_color=theme.COLOR_CYAN,
        )
        self._pitch_label.pack(side="right")

        # Separator
        ctk.CTkFrame(self._control_frame, height=2,
                      fg_color=theme.TILT_CROSSHAIR).pack(fill="x", padx=15, pady=15)

        # Tilbakestill-knapp
        self._reset_btn = ctk.CTkButton(
            self._control_frame,
            text="Tilbakestill",
            command=self._on_reset,
            font=theme.FONT_BODY,
            fg_color=theme.BG_ACCENT,
            hover_color=theme.COLOR_BLUE,
            height=40,
        )
        self._reset_btn.pack(padx=15, pady=5)

    def _on_tilt_change(self, roll: float, pitch: float) -> None:
        """Callback nar brukeren endrer tilt via sirkelen."""
        from ...geometry.pose import Pose
        from ...geometry.vector3 import Vector3

        self._update_labels(roll, pitch)
        pose = Pose(rotation=Vector3(roll, pitch, 0.0))
        self._data_bridge.set_target_pose(pose)

    def _on_mode_change(self, mode: str) -> None:
        """Callback nar brukeren bytter modus."""
        self._tilt_circle.set_live_mode(mode == "Live")

    def _on_reset(self) -> None:
        """Tilbakestill tilt til sentrum."""
        self._tilt_circle.reset()
        self._update_labels(0.0, 0.0)

    def _update_labels(self, roll: float, pitch: float) -> None:
        """Oppdater de numeriske avlesningene."""
        self._roll_label.configure(text=f"{roll:+.1f}\u00b0")
        self._pitch_label.configure(text=f"{pitch:+.1f}\u00b0")

    def update_from_state(self) -> None:
        """Oppdater visningen fra data bridge (kalles periodisk)."""
        state = self._data_bridge.get_state()

        if not self._tilt_circle.is_live:
            # Visningsmodus: Vis faktisk orientering
            self._tilt_circle.set_actual_orientation(
                state.current_pose.rotation.x,
                state.current_pose.rotation.y,
            )
            self._update_labels(
                state.current_pose.rotation.x,
                state.current_pose.rotation.y,
            )
        else:
            # Live-modus: Oppdater markor med mal-pose
            self._tilt_circle.set_target_orientation(
                state.target_pose.rotation.x,
                state.target_pose.rotation.y,
            )
