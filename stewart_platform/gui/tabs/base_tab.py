"""
base_tab.py · Felles abstrakt base for alle tab-widgets.

Gir en enhetlig signatur (`update_from_snapshot`) og referanse til
ControllerBridge. I Fase 1 tilbyr den også en enkel
"placeholder"-visning som de seks tabs bruker inntil de får sitt
endelige innhold i senere faser.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..bridge.controller_bridge import ControllerBridge
from ..bridge.state_snapshot import StateSnapshot


class BaseTab(QWidget):
    """Abstrakt base for alle hoved-tabs.

    Undertyper må overstyre `update_from_snapshot` når de får ekte
    innhold. I mellomtiden viser BaseTab en enkel live-linje slik
    at det er synlig at polling fungerer ende-til-ende.
    """

    TITLE: str = "Tab"
    PLACEHOLDER_DESCRIPTION: str = (
        "Denne tab-en er ikke implementert ennå. "
        "Live-linjen under bekrefter at snapshot-polling fungerer."
    )

    def __init__(self, bridge: ControllerBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._build_placeholder_ui()

    def _build_placeholder_ui(self) -> None:
        """Bygg en enkel placeholder-visning for Fase 1."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel(self.TITLE)
        title.setStyleSheet("font-size: 24pt; font-weight: 600;")
        layout.addWidget(title)

        desc = QLabel(self.PLACEHOLDER_DESCRIPTION)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555; font-size: 11pt;")
        layout.addWidget(desc)

        self._live = QLabel("Venter på data …")
        self._live.setStyleSheet(
            "font-family: monospace; font-size: 11pt; "
            "background: #1e1e1e; color: #8ae234; "
            "padding: 12px; border-radius: 6px;"
        )
        self._live.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._live.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._live)

        layout.addStretch()

    def update_from_snapshot(self, snapshot: StateSnapshot) -> None:
        """Oppdater visning fra StateSnapshot.

        BaseTab viser en generisk live-linje med systemstatus og
        pose. Undertyper overstyrer dette når de får ekte innhold.
        """
        pose = snapshot.current_pose
        tgt = snapshot.target_pose
        lines = [
            f"tid       : {snapshot.timestamp:15.3f}  freq: {snapshot.loop_frequency_hz:6.2f} Hz",
            f"status    : kjører={snapshot.is_running}   e-stop={snapshot.is_e_stopped}",
            f"pose (nå) : x={pose.translation.x:+7.2f}  y={pose.translation.y:+7.2f}  z={pose.translation.z:+7.2f}  "
            f"r={pose.rotation.x:+6.2f}  p={pose.rotation.y:+6.2f}  y={pose.rotation.z:+6.2f}",
            f"pose (mål): x={tgt.translation.x:+7.2f}  y={tgt.translation.y:+7.2f}  z={tgt.translation.z:+7.2f}  "
            f"r={tgt.rotation.x:+6.2f}  p={tgt.rotation.y:+6.2f}  y={tgt.rotation.z:+6.2f}",
            "servoer   : " + "  ".join(f"{a:6.2f}°" for a in snapshot.servo_angles),
            f"imu accel : {snapshot.imu_acceleration.x:+6.2f}  "
            f"{snapshot.imu_acceleration.y:+6.2f}  {snapshot.imu_acceleration.z:+6.2f}   m/s²",
            f"imu gyro  : {snapshot.imu_angular_velocity.x:+6.2f}  "
            f"{snapshot.imu_angular_velocity.y:+6.2f}  {snapshot.imu_angular_velocity.z:+6.2f}   °/s",
        ]
        self._live.setText("\n".join(lines))
