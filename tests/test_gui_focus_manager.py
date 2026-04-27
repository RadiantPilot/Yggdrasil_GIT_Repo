# test_gui_focus_manager.py
# =========================
# Tester for FocusManager og ButtonWorker. Bruker en delt
# QApplication-fixture og enkle fake-Navigables for å verifisere
# at knappehendelser ruter riktig basert på modus.

import time

import pytest
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget

from stewart_platform.gui.bridge.button_worker import ButtonWorker
from stewart_platform.gui.navigation.focus_manager import ButtonId, FocusManager
from stewart_platform.hardware.mock_buttons import MockButtons


@pytest.fixture(scope="module")
def qapp():
    """Felles QApplication-instans for alle GUI-tester i modulen."""
    app = QApplication.instance() or QApplication([])
    yield app


class FakeNavigable(QWidget):
    """Minimal Navigable som logger alle kall."""

    def __init__(self):
        super().__init__()
        self.focused = False
        self.edit = False
        self.h_history: list[int] = []
        self.v_history: list[int] = []

    def set_focused(self, focused: bool) -> None:
        self.focused = focused

    def set_edit_mode(self, edit: bool) -> None:
        self.edit = edit

    def nav_horizontal(self, delta: int) -> None:
        self.h_history.append(delta)

    def nav_vertical(self, delta: int) -> None:
        self.v_history.append(delta)


# ---------------------------------------------------------------------------
# FocusManager
# ---------------------------------------------------------------------------


class TestFocusManagerNavMode:
    """Knappetrykk i nav-mode skal flytte fokus, ikke endre verdier."""

    def test_initial_fokus_paa_forste_widget(self, qapp):
        tabs = QTabWidget()
        tab0 = QWidget()
        tabs.addTab(tab0, "T0")
        items = [FakeNavigable(), FakeNavigable()]
        estop_called = []
        fm = FocusManager(tabs, lambda: estop_called.append(True))
        fm.register_navigables(0, items)

        assert items[0].focused is True
        assert items[1].focused is False

    def test_ned_flytter_fokus_til_neste(self, qapp):
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "T0")
        items = [FakeNavigable(), FakeNavigable(), FakeNavigable()]
        fm = FocusManager(tabs, lambda: None)
        fm.register_navigables(0, items)

        fm.on_pressed(ButtonId.DOWN)

        assert items[0].focused is False
        assert items[1].focused is True

    def test_opp_paa_forste_wrapper_til_siste(self, qapp):
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "T0")
        items = [FakeNavigable(), FakeNavigable(), FakeNavigable()]
        fm = FocusManager(tabs, lambda: None)
        fm.register_navigables(0, items)

        fm.on_pressed(ButtonId.UP)

        assert items[2].focused is True

    def test_hoyre_bytter_til_neste_tab(self, qapp):
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "T0")
        tabs.addTab(QWidget(), "T1")
        fm = FocusManager(tabs, lambda: None)
        fm.register_navigables(0, [FakeNavigable()])
        fm.register_navigables(1, [FakeNavigable()])

        fm.on_pressed(ButtonId.RIGHT)

        assert tabs.currentIndex() == 1

    def test_venstre_paa_forste_tab_wrapper(self, qapp):
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "T0")
        tabs.addTab(QWidget(), "T1")
        tabs.addTab(QWidget(), "T2")
        fm = FocusManager(tabs, lambda: None)

        fm.on_pressed(ButtonId.LEFT)

        assert tabs.currentIndex() == 2

    def test_horizontal_i_navmode_endrer_ikke_widget_verdi(self, qapp):
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "T0")
        item = FakeNavigable()
        fm = FocusManager(tabs, lambda: None)
        fm.register_navigables(0, [item])

        # Selv om vi har én tab, skal venstre/høyre prøve å bytte tab
        # (wrap til samme), ikke kalle nav_horizontal.
        fm.on_pressed(ButtonId.LEFT)
        fm.on_pressed(ButtonId.RIGHT)

        assert item.h_history == []


class TestFocusManagerEditMode:
    """I edit-mode skal alle ikke-midt-knapper rutes til widget."""

    def _setup(self, qapp):
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "T0")
        item = FakeNavigable()
        fm = FocusManager(tabs, lambda: None)
        fm.register_navigables(0, [item])
        # Gå inn i edit-mode
        fm.on_pressed(ButtonId.CENTER)
        return fm, item

    def test_midt_aktiverer_edit_mode(self, qapp):
        _, item = self._setup(qapp)
        assert item.edit is True

    def test_venstre_kaller_nav_horizontal_negativ(self, qapp):
        fm, item = self._setup(qapp)
        fm.on_pressed(ButtonId.LEFT)
        assert item.h_history == [-1]

    def test_hoyre_kaller_nav_horizontal_positiv(self, qapp):
        fm, item = self._setup(qapp)
        fm.on_pressed(ButtonId.RIGHT)
        assert item.h_history == [+1]

    def test_opp_kaller_nav_vertical_negativ(self, qapp):
        fm, item = self._setup(qapp)
        fm.on_pressed(ButtonId.UP)
        assert item.v_history == [-1]

    def test_ned_kaller_nav_vertical_positiv(self, qapp):
        fm, item = self._setup(qapp)
        fm.on_pressed(ButtonId.DOWN)
        assert item.v_history == [+1]

    def test_midt_igjen_gaar_tilbake_til_navmode(self, qapp):
        fm, item = self._setup(qapp)
        fm.on_pressed(ButtonId.CENTER)
        assert item.edit is False
        assert item.focused is True


class TestFocusManagerEStop:
    """Lang-trykk på midt skal kalle estop_callback."""

    def test_lang_trykk_paa_midt_utloser_estop(self, qapp):
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "T0")
        called = []
        fm = FocusManager(tabs, lambda: called.append(True))
        fm.register_navigables(0, [FakeNavigable()])

        fm.on_long_pressed(ButtonId.CENTER)

        assert called == [True]

    def test_lang_trykk_paa_andre_knapper_ignoreres(self, qapp):
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "T0")
        called = []
        fm = FocusManager(tabs, lambda: called.append(True))
        fm.register_navigables(0, [FakeNavigable()])

        fm.on_long_pressed(ButtonId.LEFT)
        fm.on_long_pressed(ButtonId.UP)

        assert called == []


class TestFocusManagerTabBytte:
    """Bytte av tab skal forlate edit-mode og refokusere."""

    def test_edit_mode_blokkerer_tab_bytte(self, qapp):
        """I edit-mode rutes venstre/høyre til widget, ikke tab-bytte."""
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "T0")
        tabs.addTab(QWidget(), "T1")
        item0 = FakeNavigable()
        item1 = FakeNavigable()
        fm = FocusManager(tabs, lambda: None)
        fm.register_navigables(0, [item0])
        fm.register_navigables(1, [item1])

        fm.on_pressed(ButtonId.CENTER)  # enter edit
        fm.on_pressed(ButtonId.RIGHT)   # justerer verdi, bytter ikke tab

        assert tabs.currentIndex() == 0
        assert item0.h_history == [+1]

    def test_tab_bytte_etter_exit_avbryter_edit_state(self, qapp):
        """Brukeren går først ut av edit-mode, så bytter tab — første
        widget i ny tab er fokusert, ikke i edit."""
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "T0")
        tabs.addTab(QWidget(), "T1")
        item0 = FakeNavigable()
        item1 = FakeNavigable()
        fm = FocusManager(tabs, lambda: None)
        fm.register_navigables(0, [item0])
        fm.register_navigables(1, [item1])

        fm.on_pressed(ButtonId.CENTER)  # enter edit på tab 0
        fm.on_pressed(ButtonId.CENTER)  # exit edit
        assert item0.edit is False

        fm.on_pressed(ButtonId.RIGHT)   # bytt til tab 1
        assert tabs.currentIndex() == 1
        assert item1.focused is True
        assert item1.edit is False


# ---------------------------------------------------------------------------
# ButtonWorker
# ---------------------------------------------------------------------------


class TestButtonWorkerDebounce:
    """ButtonWorker._tick skal debouncer riktig."""

    def test_press_etter_debouncevindu_emitterer(self):
        drv = MockButtons()
        emitted: list[int] = []
        worker = ButtonWorker(drv, debounce_ms=10.0, long_press_ms=500.0)
        worker.button_pressed.connect(lambda i: emitted.append(i))

        drv.press(0)
        # Første tick: ny rå-tilstand, lagre tidspunkt
        worker._tick(now=0.0)
        assert emitted == []
        # Andre tick før debounce har gått — ingen emitt
        worker._tick(now=0.005)
        assert emitted == []
        # Tredje tick etter debouncen — emitt
        worker._tick(now=0.020)
        assert emitted == [0]

    def test_press_og_slipp(self):
        drv = MockButtons()
        pressed: list[int] = []
        released: list[int] = []
        worker = ButtonWorker(drv, debounce_ms=5.0, long_press_ms=500.0)
        worker.button_pressed.connect(lambda i: pressed.append(i))
        worker.button_released.connect(lambda i: released.append(i))

        drv.press(2)
        worker._tick(0.0)
        worker._tick(0.010)
        assert pressed == [2]

        drv.release(2)
        worker._tick(0.020)
        worker._tick(0.030)
        assert released == [2]

    def test_kortvarig_glitch_ignoreres(self):
        drv = MockButtons()
        pressed: list[int] = []
        worker = ButtonWorker(drv, debounce_ms=10.0, long_press_ms=500.0)
        worker.button_pressed.connect(lambda i: pressed.append(i))

        drv.press(0)
        worker._tick(0.0)
        # Slipp før debounce — endring er ikke rapportert ennå
        drv.release(0)
        worker._tick(0.005)
        worker._tick(0.020)
        assert pressed == []


class TestButtonWorkerLongPress:
    """Lang-trykk skal trigges én gang per holdt knapp."""

    def test_lang_trykk_etter_terskel(self):
        drv = MockButtons()
        long_events: list[int] = []
        released: list[int] = []
        worker = ButtonWorker(drv, debounce_ms=5.0, long_press_ms=100.0)
        worker.button_long_pressed.connect(lambda i: long_events.append(i))
        worker.button_released.connect(lambda i: released.append(i))

        drv.press(2)
        worker._tick(0.0)
        worker._tick(0.010)  # press blir stabilt
        worker._tick(0.050)  # for tidlig
        assert long_events == []

        worker._tick(0.120)  # over terskel
        assert long_events == [2]

        # Slipp — skal IKKE gi button_released siden lang-trykk allerede er
        # rapportert.
        drv.release(2)
        worker._tick(0.130)
        worker._tick(0.140)
        assert released == []

    def test_lang_trykk_emitteres_bare_en_gang(self):
        drv = MockButtons()
        long_events: list[int] = []
        worker = ButtonWorker(drv, debounce_ms=5.0, long_press_ms=50.0)
        worker.button_long_pressed.connect(lambda i: long_events.append(i))

        drv.press(0)
        for t in (0.0, 0.010, 0.060, 0.100, 0.200):
            worker._tick(t)
        assert long_events == [0]
