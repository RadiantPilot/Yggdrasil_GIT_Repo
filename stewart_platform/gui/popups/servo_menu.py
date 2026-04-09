# servo_menu.py
# =============
# Popup-vindu for direkte servostyring.
# Hovedsakelig for testing og kalibrering — bypasser IK.

from __future__ import annotations

from typing import TYPE_CHECKING, List

import customtkinter as ctk

from .. import theme

if TYPE_CHECKING:
    from ..data_bridge import GUIDataBridge


class ServoMenu(ctk.CTkToplevel):
    """Popup-vindu for individuell servokontroll.

    Viser 6 sliders (en per servo) for direkte vinkelstyring.
    Brukes for testing og kalibrering — bypasser invers kinematikk.
    """

    def __init__(self, parent: ctk.CTkBaseClass, data_bridge: GUIDataBridge) -> None:
        super().__init__(parent)
        self.title("Servokontroll (test)")
        self.geometry("400x480")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_PRIMARY)

        self._data_bridge = data_bridge
        self._sliders: List[ctk.CTkSlider] = []
        self._value_labels: List[ctk.CTkLabel] = []

        # Tittel
        ctk.CTkLabel(
            self, text="Servokontroll (test)",
            font=theme.FONT_HEADER, text_color=theme.TEXT_PRIMARY,
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            self, text="Bypasser IK — kun for testing/kalibrering",
            font=theme.FONT_SMALL, text_color=theme.COLOR_WARNING,
        ).pack(pady=(0, 10))

        # Servo-sliders
        self._slider_frame = ctk.CTkFrame(self, fg_color=theme.BG_PANEL,
                                           corner_radius=8)
        self._slider_frame.pack(fill="both", expand=True, padx=15, pady=5)

        for i in range(6):
            self._create_servo_row(i)

        # Knapper
        self._btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkButton(
            self._btn_frame, text="Alle hjem",
            font=theme.FONT_BODY,
            fg_color=theme.COLOR_BLUE,
            hover_color=theme.BG_ACCENT,
            height=36,
            command=self._go_home,
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))

        ctk.CTkButton(
            self._btn_frame, text="Frikoble alle",
            font=theme.FONT_BODY,
            fg_color=theme.COLOR_ERROR,
            hover_color="#C62828",
            height=36,
            command=self._detach_all,
        ).pack(side="right", expand=True, fill="x", padx=(5, 0))

        # Start periodisk oppdatering
        self._update_display()

    def _create_servo_row(self, index: int) -> None:
        """Opprett en rad med etikett, slider og verdi for en servo."""
        row = ctk.CTkFrame(self._slider_frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(
            row, text=f"Servo {index}:",
            font=theme.FONT_BODY, text_color=theme.TEXT_SECONDARY,
            width=70, anchor="w",
        ).pack(side="left")

        slider = ctk.CTkSlider(
            row, from_=0, to=180,
            number_of_steps=180,
            width=200,
            fg_color=theme.BG_ACCENT,
            progress_color=theme.COLOR_BLUE,
            button_color=theme.TEXT_PRIMARY,
            button_hover_color=theme.COLOR_CYAN,
        )
        slider.set(90)
        slider.pack(side="left", padx=5)
        self._sliders.append(slider)

        value_label = ctk.CTkLabel(
            row, text="90.0\u00b0",
            font=theme.FONT_MONO, text_color=theme.TEXT_PRIMARY,
            width=60,
        )
        value_label.pack(side="right")
        self._value_labels.append(value_label)

    def _go_home(self) -> None:
        """Send alle servoer til hjemmeposisjon."""
        for slider in self._sliders:
            slider.set(90)
        ctrl = self._data_bridge._controller
        if ctrl is not None and ctrl.servo_array is not None:
            ctrl.servo_array.go_home()

    def _detach_all(self) -> None:
        """Frikoble alle servoer."""
        ctrl = self._data_bridge._controller
        if ctrl is not None and ctrl.servo_array is not None:
            ctrl.servo_array.detach_all()

    def _update_display(self) -> None:
        """Oppdater slider-verdier fra faktiske servovinkler."""
        state = self._data_bridge.get_state()
        for i, angle in enumerate(state.servo_angles):
            if i < len(self._value_labels):
                self._value_labels[i].configure(text=f"{angle:.1f}\u00b0")

        if self.winfo_exists():
            self.after(200, self._update_display)
