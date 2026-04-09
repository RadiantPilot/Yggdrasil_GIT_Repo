# imu_panel.py
# ============
# IMU-sammenligning — alltid synlig under fanene.
# Viser faktisk orientering (ekstern IMU) vs. estimert (RPi-fusjon).

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from .. import theme

if TYPE_CHECKING:
    from ..data_bridge import GUIDataBridge


class IMUPanel(ctk.CTkFrame):
    """IMU-panel som viser faktisk vs. estimert orientering.

    Alltid synlig under fanene. To kolonner side-om-side:
    - Venstre: Radata fra toppplate-IMU
    - Hoyre: Estimert orientering fra IMU-fusjon
    """

    def __init__(self, parent: ctk.CTkFrame, data_bridge: GUIDataBridge) -> None:
        super().__init__(parent, fg_color=theme.BG_PANEL,
                         height=theme.IMU_PANEL_HEIGHT, corner_radius=8)
        self.pack_propagate(False)

        self._data_bridge = data_bridge

        # --- Venstre: Faktisk (ekstern IMU) ---
        self._left = ctk.CTkFrame(self, fg_color="transparent")
        self._left.pack(side="left", expand=True, fill="both", padx=(10, 5), pady=5)

        ctk.CTkLabel(
            self._left, text="Faktisk (ekstern IMU)",
            font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")

        self._left_values = ctk.CTkFrame(self._left, fg_color="transparent")
        self._left_values.pack(fill="x")

        # Orientering fra radata (beregnet)
        self._actual_orient_frame = ctk.CTkFrame(self._left_values, fg_color="transparent")
        self._actual_orient_frame.pack(fill="x")
        self._actual_roll = self._make_value_row(self._actual_orient_frame, "Roll:")
        self._actual_pitch = self._make_value_row(self._actual_orient_frame, "Pitch:")
        self._actual_yaw = self._make_value_row(self._actual_orient_frame, "Yaw:")

        # Radata (akselerasjon, gyroskop)
        self._raw_frame = ctk.CTkFrame(self._left, fg_color="transparent")
        self._raw_frame.pack(fill="x", pady=(2, 0))
        self._accel_label = ctk.CTkLabel(
            self._raw_frame, text="Accel: 0.00, 0.00, 9.81",
            font=("Consolas", 10), text_color=theme.TEXT_MUTED,
        )
        self._accel_label.pack(anchor="w")
        self._gyro_label = ctk.CTkLabel(
            self._raw_frame, text="Gyro:  0.0, 0.0, 0.0",
            font=("Consolas", 10), text_color=theme.TEXT_MUTED,
        )
        self._gyro_label.pack(anchor="w")

        # --- Separator ---
        ctk.CTkFrame(self, width=2, fg_color=theme.TILT_CROSSHAIR).pack(
            side="left", fill="y", pady=10)

        # --- Hoyre: Estimert (RPi-fusjon) ---
        self._right = ctk.CTkFrame(self, fg_color="transparent")
        self._right.pack(side="left", expand=True, fill="both", padx=(5, 10), pady=5)

        ctk.CTkLabel(
            self._right, text="Estimert (RPi-fusjon)",
            font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")

        self._right_values = ctk.CTkFrame(self._right, fg_color="transparent")
        self._right_values.pack(fill="x")

        self._est_roll = self._make_value_row(self._right_values, "Roll:")
        self._est_pitch = self._make_value_row(self._right_values, "Pitch:")
        self._est_yaw = self._make_value_row(self._right_values, "Yaw:")

    def _make_value_row(
        self, parent: ctk.CTkFrame, label: str
    ) -> ctk.CTkLabel:
        """Opprett en rad med etikett og verdi."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x")
        ctk.CTkLabel(frame, text=label, font=theme.FONT_SMALL,
                      text_color=theme.TEXT_SECONDARY, width=45,
                      anchor="w").pack(side="left")
        value_label = ctk.CTkLabel(
            frame, text="0.0\u00b0", font=theme.FONT_MONO,
            text_color=theme.TEXT_PRIMARY,
        )
        value_label.pack(side="left")
        return value_label

    def update_from_state(self) -> None:
        """Oppdater IMU-verdier fra data bridge."""
        state = self._data_bridge.get_state()

        # Faktisk orientering (fra IMU-radata)
        accel = state.imu_accel
        gyro = state.imu_gyro
        orient = state.orientation

        # Bruk fusjonert orientering som «faktisk» for toppplate
        self._actual_roll.configure(text=f"{orient.x:+.1f}\u00b0")
        self._actual_pitch.configure(text=f"{orient.y:+.1f}\u00b0")
        self._actual_yaw.configure(text=f"{orient.z:+.1f}\u00b0")

        self._accel_label.configure(
            text=f"Accel: {accel.x:.2f}, {accel.y:.2f}, {accel.z:.2f}")
        self._gyro_label.configure(
            text=f"Gyro:  {gyro.x:.1f}, {gyro.y:.1f}, {gyro.z:.1f}")

        # Estimert (fra kontrolleren)
        curr = state.current_pose.rotation
        self._est_roll.configure(text=f"{curr.x:+.1f}\u00b0")
        self._est_pitch.configure(text=f"{curr.y:+.1f}\u00b0")
        self._est_yaw.configure(text=f"{curr.z:+.1f}\u00b0")

        # Fargekod avvik
        self._color_deviation(self._actual_roll, self._est_roll,
                              orient.x, curr.x)
        self._color_deviation(self._actual_pitch, self._est_pitch,
                              orient.y, curr.y)
        self._color_deviation(self._actual_yaw, self._est_yaw,
                              orient.z, curr.z)

    def _color_deviation(
        self,
        actual_label: ctk.CTkLabel,
        est_label: ctk.CTkLabel,
        actual: float,
        estimated: float,
    ) -> None:
        """Fargekod basert pa avvik mellom faktisk og estimert."""
        diff = abs(actual - estimated)
        if diff < 1.0:
            color = theme.COLOR_OK
        elif diff < 5.0:
            color = theme.COLOR_WARNING
        else:
            color = theme.COLOR_ERROR
        actual_label.configure(text_color=color)
        est_label.configure(text_color=color)
