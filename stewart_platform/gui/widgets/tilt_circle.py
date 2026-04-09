# tilt_circle.py
# ==============
# Interaktiv tilt-sirkel for styring av roll og pitch.
# Bruker tkinter.Canvas for rask, lett rendering.
# Stotter to modi: live-styring og skrivebeskyttet visning.

from __future__ import annotations

import math
import tkinter as tk
from typing import Callable, Optional

from .. import theme


class TiltCircle(tk.Canvas):
    """Interaktiv sirkel for tilt-styring (roll/pitch).

    I live-modus kan brukeren klikke/dra inne i sirkelen
    for a sette mal-pose. Avstand fra sentrum bestemmer
    tilt-magnitude, vinkel bestemmer retning.

    I visningsmodus vises bare et kryss som indikerer
    navaerende plattformorientering.
    """

    def __init__(
        self,
        parent: tk.Widget,
        max_angle: float = 30.0,
        on_tilt_change: Optional[Callable[[float, float], None]] = None,
        **kwargs,
    ) -> None:
        """Opprett en ny tilt-sirkel.

        Args:
            parent: Tkinter-foreldrewidget.
            max_angle: Maksimal tilt-vinkel i grader (radius pa sirkelen).
            on_tilt_change: Callback ved endring, mottar (roll, pitch).
        """
        self._radius = theme.TILT_CIRCLE_RADIUS
        size = self._radius * 2 + 40  # Litt ekstra for padding
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=theme.TILT_BG,
            highlightthickness=0,
            **kwargs,
        )

        self._max_angle = max_angle
        self._on_tilt_change = on_tilt_change
        self._is_live = True
        self._center_x = size / 2
        self._center_y = size / 2

        # Navaerende verdier
        self._target_roll = 0.0
        self._target_pitch = 0.0
        self._actual_roll = 0.0
        self._actual_pitch = 0.0

        # Bind mushandlere (aktiveres/deaktiveres via modus)
        self._bind_mouse()

        # Tegn sirkelen
        self._draw()

    def _bind_mouse(self) -> None:
        """Bind mushandlere for live-styring."""
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)

    def _unbind_mouse(self) -> None:
        """Fjern mushandlere for visningsmodus."""
        self.unbind("<Button-1>")
        self.unbind("<B1-Motion>")

    def set_live_mode(self, live: bool) -> None:
        """Bytt mellom live-styring og visningsmodus.

        Args:
            live: True for live-styring, False for visning.
        """
        self._is_live = live
        if live:
            self._bind_mouse()
        else:
            self._unbind_mouse()
        self._draw()

    @property
    def is_live(self) -> bool:
        """Sjekk om sirkelen er i live-modus."""
        return self._is_live

    def set_actual_orientation(self, roll: float, pitch: float) -> None:
        """Oppdater faktisk orientering (for visningsmodus).

        Args:
            roll: Faktisk roll i grader.
            pitch: Faktisk pitch i grader.
        """
        self._actual_roll = roll
        self._actual_pitch = pitch
        self._draw()

    def set_target_orientation(self, roll: float, pitch: float) -> None:
        """Oppdater mal-orientering (for live-modus visning).

        Args:
            roll: Mal-roll i grader.
            pitch: Mal-pitch i grader.
        """
        self._target_roll = roll
        self._target_pitch = pitch
        self._draw()

    def reset(self) -> None:
        """Tilbakestill til sentrum (roll=0, pitch=0)."""
        self._target_roll = 0.0
        self._target_pitch = 0.0
        if self._on_tilt_change:
            self._on_tilt_change(0.0, 0.0)
        self._draw()

    def _pixel_to_angle(self, px: float, py: float) -> tuple[float, float]:
        """Konverter pikselposisjon til (roll, pitch) i grader."""
        dx = px - self._center_x
        dy = py - self._center_y

        # Begrens til sirkelens radius
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > self._radius:
            dx = dx * self._radius / dist
            dy = dy * self._radius / dist

        roll = (dx / self._radius) * self._max_angle
        pitch = -(dy / self._radius) * self._max_angle  # Y er invertert
        return roll, pitch

    def _angle_to_pixel(self, roll: float, pitch: float) -> tuple[float, float]:
        """Konverter (roll, pitch) i grader til pikselposisjon."""
        px = self._center_x + (roll / self._max_angle) * self._radius
        py = self._center_y - (pitch / self._max_angle) * self._radius
        return px, py

    def _on_click(self, event: tk.Event) -> None:
        """Handter klikk i sirkelen."""
        if not self._is_live:
            return
        self._handle_input(event.x, event.y)

    def _on_drag(self, event: tk.Event) -> None:
        """Handter dra i sirkelen."""
        if not self._is_live:
            return
        self._handle_input(event.x, event.y)

    def _handle_input(self, px: float, py: float) -> None:
        """Prosesser input fra mus og oppdater mal-pose."""
        roll, pitch = self._pixel_to_angle(px, py)
        self._target_roll = roll
        self._target_pitch = pitch
        if self._on_tilt_change:
            self._on_tilt_change(roll, pitch)
        self._draw()

    def _draw(self) -> None:
        """Tegn hele sirkelen pa nytt."""
        self.delete("all")
        cx, cy = self._center_x, self._center_y
        r = self._radius

        # Ytre ring (maks grense)
        self.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=theme.TILT_RING,
            width=2,
        )

        # Indre ring (80% — anbefalt omrade)
        inner_r = r * 0.8
        self.create_oval(
            cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r,
            outline=theme.TILT_INNER_RING,
            width=1,
            dash=(4, 4),
        )

        # Sentrumskryss (tynne linjer)
        self.create_line(cx - r, cy, cx + r, cy,
                         fill=theme.TILT_CROSSHAIR, width=1)
        self.create_line(cx, cy - r, cx, cy + r,
                         fill=theme.TILT_CROSSHAIR, width=1)

        # Sentrum-prikk
        self.create_oval(
            cx - 3, cy - 3, cx + 3, cy + 3,
            fill=theme.TEXT_MUTED,
            outline="",
        )

        if self._is_live:
            # Live-modus: Vis mal-posisjon som fylt sirkel
            mx, my = self._angle_to_pixel(self._target_roll, self._target_pitch)
            marker_r = 8
            self.create_oval(
                mx - marker_r, my - marker_r,
                mx + marker_r, my + marker_r,
                fill=theme.TILT_MARKER_LIVE,
                outline=theme.TEXT_PRIMARY,
                width=1,
            )
            # Modus-tekst
            self.create_text(
                cx + r - 10, cy - r + 15,
                text="LIVE",
                fill=theme.COLOR_OK,
                font=theme.FONT_SMALL,
                anchor="ne",
            )
        else:
            # Visningsmodus: Vis faktisk posisjon som kryss
            mx, my = self._angle_to_pixel(self._actual_roll, self._actual_pitch)
            cross_size = 10
            self.create_line(
                mx - cross_size, my - cross_size,
                mx + cross_size, my + cross_size,
                fill=theme.TILT_MARKER_VIEW,
                width=2,
            )
            self.create_line(
                mx - cross_size, my + cross_size,
                mx + cross_size, my - cross_size,
                fill=theme.TILT_MARKER_VIEW,
                width=2,
            )
            # Modus-tekst
            self.create_text(
                cx + r - 10, cy - r + 15,
                text="VISNING",
                fill=theme.COLOR_WARNING,
                font=theme.FONT_SMALL,
                anchor="ne",
            )
