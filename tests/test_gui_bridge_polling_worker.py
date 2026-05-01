# test_gui_bridge_polling_worker.py
# ==================================
# Tester for PollingWorker.
#
# PollingWorker kjorer paa en QThread og emitterer StateSnapshot
# med konfigurert frekvens. Vi tester at:
# - run() emitterer snapshot_ready ved hver tick.
# - stop() faar loopen til aa avslutte raskt.
# - exception fra bridge.get_snapshot() blir fanget og gjenmeldt
#   via error_occurred i stedet for aa drepe traaden stille.

import threading
import time
from unittest.mock import MagicMock

import pytest

PySide6 = pytest.importorskip("PySide6.QtCore")  # noqa: N816
from PySide6.QtCore import Qt

from stewart_platform.gui.bridge.polling_worker import PollingWorker
from stewart_platform.gui.bridge.state_snapshot import StateSnapshot


def _kjor_worker_i_traad(worker: PollingWorker, varighet_s: float) -> None:
    """Hjelper: kjor worker i bakgrunnstraad og stopp etter varighet."""
    traad = threading.Thread(target=worker.run, daemon=True)
    traad.start()
    time.sleep(varighet_s)
    worker.stop()
    traad.join(timeout=1.0)


class TestPollingWorkerSnapshot:
    """Tester at run() emitterer StateSnapshot."""

    def test_run_emitterer_snapshot_ready(self):
        """En kort kjoring skal gi minst ett snapshot."""
        bridge = MagicMock()
        bridge.get_snapshot.return_value = StateSnapshot()
        worker = PollingWorker(bridge, rate_hz=100.0)

        mottatt = []
        # DirectConnection krever ingen event-loop, slik at signalene
        # naar fram naar workeren kjorer i en plain threading.Thread.
        worker.snapshot_ready.connect(mottatt.append, Qt.DirectConnection)

        _kjor_worker_i_traad(worker, varighet_s=0.1)

        assert len(mottatt) >= 1
        assert isinstance(mottatt[0], StateSnapshot)

    def test_stop_avslutter_loopen_raskt(self):
        """stop() skal vekke event.wait slik at run() returnerer raskt."""
        bridge = MagicMock()
        bridge.get_snapshot.return_value = StateSnapshot()
        worker = PollingWorker(bridge, rate_hz=2.0)  # lang periode

        traad = threading.Thread(target=worker.run, daemon=True)
        traad.start()
        # Gi traaden tid til aa starte sin forste sleep.
        time.sleep(0.1)

        starttid = time.monotonic()
        worker.stop()
        traad.join(timeout=1.0)
        elapsed = time.monotonic() - starttid

        assert not traad.is_alive()
        # Bekreft responsiv avslutning — uten event-basert venting
        # ville stop maatte vente paa hele 0.5s sleep.
        assert elapsed < 0.5


class TestPollingWorkerFeilhaandtering:
    """Tester at unntak fanges opp og varsles via error_occurred."""

    def test_exception_fra_bridge_drep_ikke_traaden(self):
        """En exception fra get_snapshot skal logges, ikke drepe loopen."""
        bridge = MagicMock()

        # Skift mellom feil og suksess slik at vi vet vi gaar gjennom
        # baade error- og snapshot-grenen — uten aa tomme en
        # side_effect-liste.
        kall_teller = {"n": 0}

        def get_snapshot():
            kall_teller["n"] += 1
            if kall_teller["n"] % 2 == 1:
                raise RuntimeError("test-feil")
            return StateSnapshot()

        bridge.get_snapshot.side_effect = get_snapshot
        worker = PollingWorker(bridge, rate_hz=100.0)

        mottatt_snapshot = []
        mottatt_feil = []
        worker.snapshot_ready.connect(mottatt_snapshot.append, Qt.DirectConnection)
        worker.error_occurred.connect(mottatt_feil.append, Qt.DirectConnection)

        _kjor_worker_i_traad(worker, varighet_s=0.1)

        assert len(mottatt_feil) >= 1
        assert "test-feil" in mottatt_feil[0]
        # Loopen skal ha fortsatt og hentet flere snapshots etter feilen.
        assert len(mottatt_snapshot) >= 1

    def test_rate_hz_klemmes_til_minst_en_hz(self):
        """rate_hz under 1 skal klemmes til 1 for aa unngaa division-by-zero."""
        bridge = MagicMock()
        bridge.get_snapshot.return_value = StateSnapshot()
        worker = PollingWorker(bridge, rate_hz=0.0)
        assert worker._rate_hz >= 1.0
