# platform_3d.py
# ==============
# Fane 2: 3D-visualisering av Stewart-plattformen.
# Embedded matplotlib-plot som oppdateres live.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .. import theme
from ..widgets.platform_renderer import PlatformRenderer

if TYPE_CHECKING:
    from ..data_bridge import GUIDataBridge
    from ...geometry.platform_geometry import PlatformGeometry


class Platform3DView(ctk.CTkFrame):
    """Fane for 3D-visualisering av plattformen.

    Viser en interaktiv 3D-modell av Stewart-plattformen
    som oppdateres i sanntid. Brukeren kan rotere visningen
    med musen (matplotlib innebygd).
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        data_bridge: GUIDataBridge,
        geometry: Optional[PlatformGeometry] = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._data_bridge = data_bridge
        self._geometry = geometry

        # --- Hovedinnhold ---
        self._content = ctk.CTkFrame(self, fg_color=theme.BG_PANEL,
                                      corner_radius=10)
        self._content.pack(expand=True, fill="both", padx=10, pady=10)

        # Tittel og knapper
        self._header = ctk.CTkFrame(self._content, fg_color="transparent")
        self._header.pack(fill="x", padx=10, pady=(10, 0))

        ctk.CTkLabel(
            self._header,
            text="3D-visning",
            font=theme.FONT_HEADER,
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        self._reset_cam_btn = ctk.CTkButton(
            self._header,
            text="Nullstill kamera",
            command=self._reset_camera,
            font=theme.FONT_SMALL,
            fg_color=theme.BG_ACCENT,
            hover_color=theme.COLOR_BLUE,
            width=130,
            height=30,
        )
        self._reset_cam_btn.pack(side="right")

        # Matplotlib-figur
        self._fig = Figure(figsize=(7, 5), dpi=100)
        self._renderer = PlatformRenderer(self._fig)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self._content)
        self._canvas.get_tk_widget().pack(expand=True, fill="both", padx=10, pady=10)

        # Tegn initialvisning med standard geometri
        self._draw_initial()

    def set_geometry(self, geometry: PlatformGeometry) -> None:
        """Sett plattformgeometri for korrekte posisjoner.

        Args:
            geometry: PlatformGeometry-instans.
        """
        self._geometry = geometry

    def _draw_initial(self) -> None:
        """Tegn plattformen i hjemmeposisjon."""
        if self._geometry is not None:
            from ...geometry.pose import Pose
            pose = Pose.home()
            base = self._geometry.get_base_joints()
            top = self._geometry.get_platform_joints_world(pose)
            self._renderer.update(base, top)
            self._canvas.draw_idle()

    def _reset_camera(self) -> None:
        """Tilbakestill kameravinkel."""
        self._renderer.reset_camera()
        self._canvas.draw_idle()

    def update_from_state(self) -> None:
        """Oppdater 3D-visningen fra data bridge (kalles periodisk)."""
        if self._geometry is None:
            return

        state = self._data_bridge.get_state()
        base = self._geometry.get_base_joints()
        top = self._geometry.get_platform_joints_world(state.current_pose)
        self._renderer.update(base, top)
        self._canvas.draw_idle()
