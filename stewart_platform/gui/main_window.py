"""
main_window.py · QMainWindow — rotkomponenten for GUI-et.

Inneholder QTabWidget med de 6 tabbene (Oversikt, Pose, PID, IMU,
Konfig, Sikkerhet) og en topbar med grunnleggende kontroller.
I Fase 1 er tabs bare placeholder-widgets med oppdatert klokke og
status — det er nok til å bekrefte at polling-kjeden fungerer.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from .bridge.controller_bridge import ControllerBridge
from .bridge.state_snapshot import StateSnapshot
from .tabs.config_tab import ConfigTab
from .tabs.imu_tab import ImuTab
from .tabs.overview_tab import OverviewTab
from .tabs.pid_tuning_tab import PidTuningTab
from .tabs.pose_control_tab import PoseControlTab
from .tabs.safety_tab import SafetyTab
from .utils.theme import ThemeManager


class MainWindow(QMainWindow):
    """Hovedvindu for Yggdrasil GUI."""

    def __init__(self, bridge: ControllerBridge) -> None:
        """Opprett hovedvinduet.

        Args:
            bridge: ControllerBridge som alle tabs får referanse til.
        """
        super().__init__()
        self._bridge = bridge
        self.setWindowTitle("Yggdrasil — Stewart-plattform")
        self.resize(1400, 900)

        self._build_toolbar()
        self._build_tabs()
        self._build_statusbar()
        self._install_shortcuts()

    # ------------------------------------------------------------------
    # Oppbygging
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        """Bygger den globale topbaren med Start/Stop/Home/E-STOP."""
        bar = QToolBar("Hovedkontroller")
        bar.setMovable(False)
        self.addToolBar(bar)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._btn_start = QPushButton("▶ Start")
        self._btn_start.clicked.connect(self._on_start_clicked)
        layout.addWidget(self._btn_start)

        self._btn_stop = QPushButton("■ Stopp")
        self._btn_stop.clicked.connect(self._on_stop_clicked)
        layout.addWidget(self._btn_stop)

        self._btn_home = QPushButton("⌂ Home")
        self._btn_home.setToolTip(
            "Sett mål-pose til hvilestilling (0,0,0) og be servoene "
            "kjøre til home-vinkel fra config."
        )
        self._btn_home.clicked.connect(self._on_home_clicked)
        layout.addWidget(self._btn_home)

        layout.addStretch()

        # Tema-bytte — skifter mellom lys og mørk modus
        self._btn_theme = QPushButton("🌙 Mørk")
        self._btn_theme.setToolTip("Bytt mellom lys og mørk modus")
        self._btn_theme.setCheckable(True)
        self._btn_theme.setChecked(ThemeManager.instance().current.name == "dark")
        self._update_theme_button_label()
        self._btn_theme.clicked.connect(self._on_theme_toggle)
        layout.addWidget(self._btn_theme)

        self._lbl_mode = QLabel("Modus: —")
        self._lbl_mode.setStyleSheet("color: #666; padding: 0 12px;")
        layout.addWidget(self._lbl_mode)

        self._lbl_rate = QLabel("— Hz")
        self._lbl_rate.setStyleSheet("color: #666; padding: 0 12px;")
        layout.addWidget(self._lbl_rate)

        self._btn_estop = QPushButton("E-STOP (F1)")
        self._btn_estop.setStyleSheet(
            "QPushButton { background: #c0392b; color: white; "
            "font-weight: bold; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background: #a93226; }"
        )
        self._btn_estop.clicked.connect(self._on_estop_clicked)
        layout.addWidget(self._btn_estop)

        bar.addWidget(container)

        # Oppdater modus-etiketten med en gang
        self._lbl_mode.setText(
            "Modus: SIMULERT" if self._bridge.is_mock else "Modus: HARDWARE"
        )

    def _build_tabs(self) -> None:
        """Bygger QTabWidget med de 6 hovedtabbene."""
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._tab_overview = OverviewTab(self._bridge)
        self._tab_pose = PoseControlTab(self._bridge)
        self._tab_pid = PidTuningTab(self._bridge)
        self._tab_imu = ImuTab(self._bridge)
        self._tab_config = ConfigTab(self._bridge)
        self._tab_safety = SafetyTab(self._bridge)

        self._tabs.addTab(self._tab_overview, "Oversikt")
        self._tabs.addTab(self._tab_pose, "Pose-kontroll")
        self._tabs.addTab(self._tab_pid, "PID-tuning")
        self._tabs.addTab(self._tab_imu, "IMU")
        self._tabs.addTab(self._tab_config, "Konfig")
        self._tabs.addTab(self._tab_safety, "Sikkerhet")

        self._tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self._tabs)

    def _build_statusbar(self) -> None:
        """Enkel statusbar nederst — bruker kan se siste hendelse."""
        bar = QStatusBar()
        self.setStatusBar(bar)
        bar.showMessage("Klar.")

    def _install_shortcuts(self) -> None:
        """Globale hurtigtaster."""
        # F1 = E-STOP
        sc_estop = QShortcut(QKeySequence("F1"), self)
        sc_estop.activated.connect(self._on_estop_clicked)

    # ------------------------------------------------------------------
    # Signal-slots
    # ------------------------------------------------------------------

    @Slot(object)
    def on_snapshot(self, snapshot: StateSnapshot) -> None:
        """Mottar nye StateSnapshots fra PollingWorker og ruter til aktiv tab.

        For å spare CPU oppdaterer vi kun den aktivt synlige tab-en.
        Alle tabs er likevel abonnenter — metoden `update_from_snapshot`
        er idempotent og kan trygt kalles oftere.
        """
        self._lbl_rate.setText(f"{snapshot.loop_frequency_hz:5.1f} Hz")

        current = self._tabs.currentWidget()
        if hasattr(current, "update_from_snapshot"):
            current.update_from_snapshot(snapshot)

    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        """Gi ny aktiv tab et snapshot med en gang så den ikke står tom."""
        snapshot = self._bridge.get_snapshot()
        widget = self._tabs.widget(index)
        if hasattr(widget, "update_from_snapshot"):
            widget.update_from_snapshot(snapshot)

    @Slot()
    def _on_start_clicked(self) -> None:
        self._bridge.request_start()
        self.statusBar().showMessage("Start-kommando sendt.", 3000)

    @Slot()
    def _on_stop_clicked(self) -> None:
        self._bridge.request_stop()
        self.statusBar().showMessage("Stopp-kommando sendt.", 3000)

    @Slot()
    def _on_home_clicked(self) -> None:
        self._bridge.request_home()
        self.statusBar().showMessage("Home-kommando sendt — mål-pose satt til (0,0,0).", 3000)

    @Slot()
    def _on_theme_toggle(self) -> None:
        """Bytt mellom lys og mørk modus."""
        new_theme = ThemeManager.instance().toggle()
        self._btn_theme.setChecked(new_theme.name == "dark")
        self._update_theme_button_label()
        self.statusBar().showMessage(
            f"Tema: {'mørk' if new_theme.name == 'dark' else 'lys'}", 2000,
        )

    def _update_theme_button_label(self) -> None:
        """Sett label som antyder hva klikk vil gjøre."""
        if ThemeManager.instance().current.name == "dark":
            self._btn_theme.setText("☀ Lys")
        else:
            self._btn_theme.setText("🌙 Mørk")

    @Slot()
    def _on_estop_clicked(self) -> None:
        self._bridge.trigger_e_stop("Manuell E-STOP fra GUI")
        QMessageBox.warning(
            self,
            "Nødstopp utløst",
            "E-STOP er aktivert. Servoene er frikoblet.\n\n"
            "Gå til Sikkerhet-fanen for å tilbakestille når farekilden er borte.",
        )
        self.statusBar().showMessage("E-STOP aktivert.", 0)
