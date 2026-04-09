# app.py
# ======
# Hovedvindu for Stewart-plattformens GUI.
# Kobler sammen alle komponenter: toppbar, faner, IMU-panel,
# sikkerhetsbar, og popup-menyer i et CustomTkinter-vindu.

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import customtkinter as ctk

from . import theme
from .data_bridge import GUIDataBridge
from .components.top_bar import TopBar
from .components.safety_bar import SafetyBar
from .components.imu_panel import IMUPanel
from .views.tilt_control import TiltControlView
from .views.platform_3d import Platform3DView

if TYPE_CHECKING:
    from ..config.platform_config import PlatformConfig
    from ..control.motion_controller import MotionController
    from ..geometry.platform_geometry import PlatformGeometry


class StewartPlatformApp(ctk.CTk):
    """Hovedapplikasjon for Stewart-plattformens GUI.

    Setter opp vinduet med:
    - Toppbar (tilstand, start/stopp, menyknapper)
    - 2 hovedfaner (Styring, 3D-visning)
    - IMU-panel (alltid synlig)
    - Sikkerhetsbar (NODSTOPP, alltid synlig)
    - Popup-menyer for servoer og innstillinger
    """

    def __init__(
        self,
        config: Optional[PlatformConfig] = None,
        controller: Optional[MotionController] = None,
        geometry: Optional[PlatformGeometry] = None,
    ) -> None:
        """Opprett hovedvinduet.

        Args:
            config: Plattformkonfigurasjon (for innstillinger).
            controller: MotionController (for live-data). None for demo-modus.
            geometry: PlatformGeometry (for 3D-visning).
        """
        super().__init__()

        # Konfigurer vindu
        self.title("Stewart Platform")
        self.geometry(f"{theme.WINDOW_WIDTH}x{theme.WINDOW_HEIGHT}")
        self.minsize(900, 600)
        self.configure(fg_color=theme.BG_PRIMARY)

        # CustomTkinter-tema
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._config = config
        self._geometry = geometry

        # Data bridge
        self._data_bridge = GUIDataBridge()
        if controller is not None:
            self._data_bridge.connect(controller)

        # Referanser til popup-vinduer
        self._servo_menu: Optional[ctk.CTkToplevel] = None
        self._settings_window: Optional[ctk.CTkToplevel] = None

        # --- Bygg layout ---
        self._build_ui()

        # Start periodisk oppdatering
        self._schedule_update()

    def _build_ui(self) -> None:
        """Bygg hele GUI-layouten."""

        # Toppbar
        self._top_bar = TopBar(
            self, self._data_bridge,
            on_settings=self._open_settings,
            on_servo_menu=self._open_servo_menu,
        )
        self._top_bar.pack(fill="x")

        # Hovedomrade (faner + IMU-panel)
        self._main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._main_frame.pack(fill="both", expand=True)

        # Fane-system
        self._tabview = ctk.CTkTabview(
            self._main_frame,
            fg_color=theme.BG_PANEL,
            segmented_button_fg_color=theme.BG_ACCENT,
            segmented_button_selected_color=theme.COLOR_BLUE,
            segmented_button_unselected_color=theme.BG_ACCENT,
        )
        self._tabview.pack(fill="both", expand=True, padx=10, pady=(5, 0))

        self._tabview.add("Styring")
        self._tabview.add("3D-visning")

        # Fane 1: Tilt-styring
        self._tilt_view = TiltControlView(
            self._tabview.tab("Styring"),
            self._data_bridge,
        )
        self._tilt_view.pack(fill="both", expand=True)

        # Fane 2: 3D-visning
        self._3d_view = Platform3DView(
            self._tabview.tab("3D-visning"),
            self._data_bridge,
            geometry=self._geometry,
        )
        self._3d_view.pack(fill="both", expand=True)

        # IMU-panel (alltid synlig under fanene)
        self._imu_panel = IMUPanel(self._main_frame, self._data_bridge)
        self._imu_panel.pack(fill="x", padx=10, pady=(5, 5))

        # Sikkerhetsbar (bunn)
        self._safety_bar = SafetyBar(self, self._data_bridge)
        self._safety_bar.pack(fill="x")

    def _open_servo_menu(self) -> None:
        """Apne servo-kontrollvinduet."""
        if self._servo_menu is None or not self._servo_menu.winfo_exists():
            from .popups.servo_menu import ServoMenu
            self._servo_menu = ServoMenu(self, self._data_bridge)
        else:
            self._servo_menu.focus()

    def _open_settings(self) -> None:
        """Apne innstillingsvinduet."""
        if self._settings_window is None or not self._settings_window.winfo_exists():
            from .popups.settings_window import SettingsWindow
            self._settings_window = SettingsWindow(
                self, self._data_bridge, self._config)
        else:
            self._settings_window.focus()

    def _schedule_update(self) -> None:
        """Planlegg periodisk oppdatering av GUI."""
        self._update_gui()
        self.after(theme.GUI_UPDATE_INTERVAL_MS, self._schedule_update)

    def _update_gui(self) -> None:
        """Oppdater alle GUI-komponenter fra data bridge."""
        # Oppdater data fra kontroller forst
        self._data_bridge.update_from_controller()

        # Oppdater permanente komponenter
        self._top_bar.update_from_state()
        self._safety_bar.update_from_state()
        self._imu_panel.update_from_state()

        # Oppdater kun aktiv fane
        current_tab = self._tabview.get()
        if current_tab == "Styring":
            self._tilt_view.update_from_state()
        elif current_tab == "3D-visning":
            self._3d_view.update_from_state()


def run_demo() -> None:
    """Kjor GUI i demo-modus uten maskinvare.

    Nyttig for utvikling og testing pa PC uten Raspberry Pi.
    Bruker standardkonfigurasjon og simulert data.
    """
    from ..config.platform_config import PlatformConfig
    from ..geometry.platform_geometry import PlatformGeometry

    config = PlatformConfig()
    geometry = PlatformGeometry(config)

    app = StewartPlatformApp(config=config, geometry=geometry)
    app.mainloop()


if __name__ == "__main__":
    run_demo()
