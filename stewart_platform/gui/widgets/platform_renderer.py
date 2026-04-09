# platform_renderer.py
# ====================
# Matplotlib-basert 3D-renderer for Stewart-plattformen.
# Tegner bunnplate, toppplate, bein og servoarmer.
# Oppdateres live fra data bridge.

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from .. import theme

if TYPE_CHECKING:
    from ...geometry.vector3 import Vector3


class PlatformRenderer:
    """3D-renderer for Stewart-plattformen med matplotlib.

    Tegner plattformen som to polygoner (bunn- og toppplate)
    forbundet med 6 bein. Oppdateres effektivt ved a flytte
    eksisterende linjer i stedet for a tegne alt pa nytt.
    """

    def __init__(self, figure: Figure) -> None:
        """Opprett renderer pa en matplotlib-figur.

        Args:
            figure: Matplotlib Figure som plattformen tegnes pa.
        """
        self._fig = figure
        self._fig.patch.set_facecolor(theme.BG_PRIMARY)

        self._ax = self._fig.add_subplot(111, projection="3d")
        self._ax.set_facecolor(theme.BG_PRIMARY)

        # Konfigurer akser
        self._ax.set_xlabel("X (mm)", color=theme.TEXT_SECONDARY, fontsize=9)
        self._ax.set_ylabel("Y (mm)", color=theme.TEXT_SECONDARY, fontsize=9)
        self._ax.set_zlabel("Z (mm)", color=theme.TEXT_SECONDARY, fontsize=9)
        self._ax.tick_params(colors=theme.TEXT_MUTED, labelsize=8)

        # Standard visningsvinkel
        self._default_elev = 25
        self._default_azim = -60
        self._ax.view_init(elev=self._default_elev, azim=self._default_azim)

        # Linjer og flater — opprettes ved forste tegning
        self._base_poly: Optional[Poly3DCollection] = None
        self._top_poly: Optional[Poly3DCollection] = None
        self._leg_lines: List = []
        self._initialized = False

    def reset_camera(self) -> None:
        """Tilbakestill kameravinkel til standard."""
        self._ax.view_init(elev=self._default_elev, azim=self._default_azim)

    def update(
        self,
        base_joints: List[Vector3],
        platform_joints: List[Vector3],
    ) -> None:
        """Oppdater 3D-visningen med nye leddposisjoner.

        Args:
            base_joints: 6 basepunkter (Vector3).
            platform_joints: 6 toppplatepunkter i verdenskoordinater.
        """
        # Konverter til numpy
        base = np.array([[j.x, j.y, j.z] for j in base_joints])
        top = np.array([[j.x, j.y, j.z] for j in platform_joints])

        self._ax.cla()

        # Konfigurer akser pa nytt etter clear
        self._ax.set_facecolor(theme.BG_PRIMARY)
        self._ax.set_xlabel("X (mm)", color=theme.TEXT_SECONDARY, fontsize=9)
        self._ax.set_ylabel("Y (mm)", color=theme.TEXT_SECONDARY, fontsize=9)
        self._ax.set_zlabel("Z (mm)", color=theme.TEXT_SECONDARY, fontsize=9)
        self._ax.tick_params(colors=theme.TEXT_MUTED, labelsize=8)

        # Sett akseomrade
        all_pts = np.vstack([base, top])
        margin = 40
        x_range = [all_pts[:, 0].min() - margin, all_pts[:, 0].max() + margin]
        y_range = [all_pts[:, 1].min() - margin, all_pts[:, 1].max() + margin]
        z_range = [-20, all_pts[:, 2].max() + margin]
        self._ax.set_xlim(x_range)
        self._ax.set_ylim(y_range)
        self._ax.set_zlim(z_range)

        # Tegn bunnplate (polygon)
        base_poly = Poly3DCollection(
            [base.tolist()],
            alpha=0.3,
            facecolor=theme.COLOR_BASE_PLATE,
            edgecolor=theme.TEXT_SECONDARY,
            linewidth=1,
        )
        self._ax.add_collection3d(base_poly)

        # Tegn toppplate (polygon)
        top_poly = Poly3DCollection(
            [top.tolist()],
            alpha=0.4,
            facecolor=theme.COLOR_TOP_PLATE,
            edgecolor=theme.TEXT_PRIMARY,
            linewidth=1,
        )
        self._ax.add_collection3d(top_poly)

        # Tegn bein
        for i in range(6):
            self._ax.plot(
                [base[i, 0], top[i, 0]],
                [base[i, 1], top[i, 1]],
                [base[i, 2], top[i, 2]],
                color=theme.COLOR_LEG_OK,
                linewidth=2,
            )

        # Tegn leddpunkter
        self._ax.scatter(
            base[:, 0], base[:, 1], base[:, 2],
            color=theme.TEXT_PRIMARY,
            s=25,
            depthshade=False,
        )
        self._ax.scatter(
            top[:, 0], top[:, 1], top[:, 2],
            color=theme.COLOR_CYAN,
            s=25,
            depthshade=False,
        )

        # Fjern bakgrunnsruter for renere utseende
        self._ax.xaxis.pane.fill = False
        self._ax.yaxis.pane.fill = False
        self._ax.zaxis.pane.fill = False
        self._ax.xaxis.pane.set_edgecolor(theme.TILT_CROSSHAIR)
        self._ax.yaxis.pane.set_edgecolor(theme.TILT_CROSSHAIR)
        self._ax.zaxis.pane.set_edgecolor(theme.TILT_CROSSHAIR)
        self._ax.grid(True, alpha=0.2)
