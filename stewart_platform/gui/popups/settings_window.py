# settings_window.py
# ==================
# Popup-vindu for innstillinger: PID-tuning, sikkerhetsgrenser
# og konfigurasjon. Inneholder 3 under-faner.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from .. import theme

if TYPE_CHECKING:
    from ..data_bridge import GUIDataBridge
    from ...config.platform_config import PlatformConfig


class SettingsWindow(ctk.CTkToplevel):
    """Innstillingsvindu med 3 faner: PID, Sikkerhet, Konfig.

    Apnes via tannhjul-knapp i toppbar. Lar brukeren justere
    PID-parametere i sanntid, endre sikkerhetsgrenser, og
    lagre/laste konfigurasjon fra YAML.
    """

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        data_bridge: GUIDataBridge,
        config: Optional[PlatformConfig] = None,
    ) -> None:
        super().__init__(parent)
        self.title("Innstillinger")
        self.geometry("550x520")
        self.configure(fg_color=theme.BG_PRIMARY)

        self._data_bridge = data_bridge
        self._config = config

        # Fane-system
        self._tabview = ctk.CTkTabview(self, fg_color=theme.BG_PANEL)
        self._tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self._tabview.add("PID-tuning")
        self._tabview.add("Sikkerhet")
        self._tabview.add("Konfigurasjon")

        self._build_pid_tab()
        self._build_safety_tab()
        self._build_config_tab()

    # --- PID-tuning ---

    def _build_pid_tab(self) -> None:
        """Bygg PID-tuning-fanen."""
        tab = self._tabview.tab("PID-tuning")

        ctk.CTkLabel(tab, text="PID-regulatorforsterkning",
                      font=theme.FONT_HEADER, text_color=theme.TEXT_PRIMARY,
                      ).pack(pady=(10, 15))

        # Hent navaerende verdier
        kp_val = 1.0
        ki_val = 0.0
        kd_val = 0.0
        if self._config is not None:
            kp_val = self._config.pid_gains.kp
            ki_val = self._config.pid_gains.ki
            kd_val = self._config.pid_gains.kd

        self._kp_slider, self._kp_entry = self._make_param_row(
            tab, "Kp (proporsjonal):", 0.0, 10.0, kp_val)
        self._ki_slider, self._ki_entry = self._make_param_row(
            tab, "Ki (integral):", 0.0, 5.0, ki_val)
        self._kd_slider, self._kd_entry = self._make_param_row(
            tab, "Kd (derivat):", 0.0, 5.0, kd_val)

        # Knapper
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkButton(
            btn_frame, text="Bruk", width=100, height=36,
            font=theme.FONT_BODY,
            fg_color=theme.COLOR_OK, hover_color="#388E3C",
            command=self._apply_pid,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Nullstill PID", width=120, height=36,
            font=theme.FONT_BODY,
            fg_color=theme.COLOR_WARNING, hover_color="#F57F17",
            text_color=theme.BG_PRIMARY,
            command=self._reset_pid,
        ).pack(side="left", padx=5)

    def _make_param_row(
        self,
        parent: ctk.CTkFrame,
        label: str,
        min_val: float,
        max_val: float,
        default: float,
    ) -> tuple[ctk.CTkSlider, ctk.CTkEntry]:
        """Opprett en rad med etikett, slider og numerisk input."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(frame, text=label, font=theme.FONT_BODY,
                      text_color=theme.TEXT_SECONDARY,
                      width=160, anchor="w").pack(side="left")

        entry_var = ctk.StringVar(value=f"{default:.2f}")
        entry = ctk.CTkEntry(
            frame, width=70, font=theme.FONT_MONO,
            textvariable=entry_var,
        )
        entry.pack(side="right", padx=(5, 0))

        slider = ctk.CTkSlider(
            frame, from_=min_val, to=max_val,
            width=200,
            fg_color=theme.BG_ACCENT,
            progress_color=theme.COLOR_BLUE,
            button_color=theme.TEXT_PRIMARY,
        )
        slider.set(default)
        slider.pack(side="right", padx=5)

        # Synkroniser slider og entry
        def on_slider_change(val: float) -> None:
            entry_var.set(f"{val:.2f}")

        slider.configure(command=on_slider_change)

        return slider, entry

    def _apply_pid(self) -> None:
        """Bruk PID-verdier fra sliders."""
        from ...config.platform_config import PIDGains

        try:
            kp = float(self._kp_entry.get())
            ki = float(self._ki_entry.get())
            kd = float(self._kd_entry.get())
        except ValueError:
            return

        gains = PIDGains(kp=kp, ki=ki, kd=kd)

        ctrl = self._data_bridge._controller
        if ctrl is not None and ctrl.pose_controller is not None:
            ctrl.pose_controller.set_gains(gains)

    def _reset_pid(self) -> None:
        """Nullstill PID-regulatoren."""
        ctrl = self._data_bridge._controller
        if ctrl is not None and ctrl.pose_controller is not None:
            ctrl.pose_controller.reset()

    # --- Sikkerhetsgrenser ---

    def _build_safety_tab(self) -> None:
        """Bygg sikkerhetsfanen."""
        tab = self._tabview.tab("Sikkerhet")

        ctk.CTkLabel(tab, text="Sikkerhetsgrenser",
                      font=theme.FONT_HEADER, text_color=theme.TEXT_PRIMARY,
                      ).pack(pady=(10, 15))

        # Hent navaerende verdier
        sc = None
        if self._config is not None:
            sc = self._config.safety_config

        self._max_trans_slider, self._max_trans_entry = self._make_param_row(
            tab, "Maks translasjon (mm):", 10.0, 100.0,
            sc.max_translation_mm if sc else 50.0)
        self._max_rot_slider, self._max_rot_entry = self._make_param_row(
            tab, "Maks rotasjon (\u00b0):", 5.0, 45.0,
            sc.max_rotation_deg if sc else 30.0)
        self._max_vel_slider, self._max_vel_entry = self._make_param_row(
            tab, "Maks hastighet (mm/s):", 10.0, 200.0,
            sc.max_velocity_mm_per_s if sc else 100.0)
        self._max_angvel_slider, self._max_angvel_entry = self._make_param_row(
            tab, "Maks vinkelhast. (\u00b0/s):", 10.0, 120.0,
            sc.max_angular_velocity_deg_per_s if sc else 60.0)

        # Bruk-knapp
        ctk.CTkButton(
            tab, text="Bruk", width=100, height=36,
            font=theme.FONT_BODY,
            fg_color=theme.COLOR_OK, hover_color="#388E3C",
            command=self._apply_safety,
        ).pack(pady=15)

    def _apply_safety(self) -> None:
        """Bruk nye sikkerhetsgrenser."""
        if self._config is None:
            return
        try:
            self._config.safety_config.max_translation_mm = float(
                self._max_trans_entry.get())
            self._config.safety_config.max_rotation_deg = float(
                self._max_rot_entry.get())
            self._config.safety_config.max_velocity_mm_per_s = float(
                self._max_vel_entry.get())
            self._config.safety_config.max_angular_velocity_deg_per_s = float(
                self._max_angvel_entry.get())
        except ValueError:
            pass

    # --- Konfigurasjon ---

    def _build_config_tab(self) -> None:
        """Bygg konfigurasjonsfanen."""
        tab = self._tabview.tab("Konfigurasjon")

        ctk.CTkLabel(tab, text="Plattformkonfigurasjon",
                      font=theme.FONT_HEADER, text_color=theme.TEXT_PRIMARY,
                      ).pack(pady=(10, 15))

        # Geometri-visning (skrivebeskyttet)
        info_frame = ctk.CTkFrame(tab, fg_color=theme.BG_ACCENT, corner_radius=8)
        info_frame.pack(fill="x", padx=15, pady=5)

        if self._config is not None:
            params = [
                ("Baseradius:", f"{self._config.base_radius:.1f} mm"),
                ("Plattformradius:", f"{self._config.platform_radius:.1f} mm"),
                ("Staglengde:", f"{self._config.rod_length:.1f} mm"),
                ("Servoarmlengde:", f"{self._config.servo_horn_length:.1f} mm"),
                ("Hjemmehoyde:", f"{self._config.home_height:.1f} mm"),
                ("Kontrollfrekvens:", f"{self._config.control_loop_rate_hz:.0f} Hz"),
            ]
        else:
            params = [("Ingen konfigurasjon lastet", "")]

        for label_text, value_text in params:
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(row, text=label_text, font=theme.FONT_SMALL,
                          text_color=theme.TEXT_SECONDARY,
                          width=140, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value_text, font=theme.FONT_MONO,
                          text_color=theme.TEXT_PRIMARY).pack(side="right")

        # Fil-operasjoner
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkButton(
            btn_frame, text="Lagre til fil", width=130, height=36,
            font=theme.FONT_BODY,
            fg_color=theme.COLOR_BLUE, hover_color=theme.BG_ACCENT,
            command=self._save_config,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Last fra fil", width=130, height=36,
            font=theme.FONT_BODY,
            fg_color=theme.BG_ACCENT, hover_color=theme.COLOR_BLUE,
            command=self._load_config,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Valider", width=100, height=36,
            font=theme.FONT_BODY,
            fg_color=theme.COLOR_OK, hover_color="#388E3C",
            command=self._validate_config,
        ).pack(side="left", padx=5)

        # Status-tekst
        self._config_status = ctk.CTkLabel(
            tab, text="", font=theme.FONT_SMALL,
            text_color=theme.COLOR_OK,
        )
        self._config_status.pack(pady=5)

    def _save_config(self) -> None:
        """Lagre konfigurasjon til YAML-fil."""
        from tkinter import filedialog
        if self._config is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml"), ("Alle filer", "*.*")],
        )
        if path:
            self._config.save(path)
            self._config_status.configure(
                text=f"Lagret til {path}", text_color=theme.COLOR_OK)

    def _load_config(self) -> None:
        """Last konfigurasjon fra YAML-fil."""
        from tkinter import filedialog
        from ...config.platform_config import PlatformConfig

        path = filedialog.askopenfilename(
            filetypes=[("YAML", "*.yaml"), ("Alle filer", "*.*")],
        )
        if path:
            try:
                self._config = PlatformConfig.load(path)
                self._config_status.configure(
                    text=f"Lastet fra {path}", text_color=theme.COLOR_OK)
            except Exception as e:
                self._config_status.configure(
                    text=f"Feil: {e}", text_color=theme.COLOR_ERROR)

    def _validate_config(self) -> None:
        """Valider navaerende konfigurasjon."""
        if self._config is None:
            self._config_status.configure(
                text="Ingen konfigurasjon lastet", text_color=theme.COLOR_WARNING)
            return
        try:
            self._config.validate()
            self._config_status.configure(
                text="Konfigurasjon er gyldig", text_color=theme.COLOR_OK)
        except ValueError as e:
            self._config_status.configure(
                text=f"Ugyldig: {e}", text_color=theme.COLOR_ERROR)
