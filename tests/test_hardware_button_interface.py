# test_hardware_button_interface.py
# =================================
# Tester for ButtonInterface, MockButtons og AttinyI2CButtons.
# RPiGPIOButtons testes ikke her siden gpiozero krever ekte
# GPIO-tilgang — den dekkes manuelt på RPi.

import threading

import pytest

from stewart_platform.hardware.attiny_i2c_buttons import AttinyI2CButtons
from stewart_platform.hardware.button_interface import ButtonInterface
from stewart_platform.hardware.mock_buttons import MockButtons


class TestButtonInterfaceKontrakt:
    """Verifiser at MockButtons oppfyller ButtonInterface."""

    def test_mock_kan_opprettes(self):
        btns = MockButtons()
        assert isinstance(btns, ButtonInterface)

    def test_read_returnerer_int(self):
        btns = MockButtons()
        assert isinstance(btns.read(), int)

    def test_num_buttons_er_5(self):
        assert ButtonInterface.NUM_BUTTONS == 5


class TestMockButtonsOppforsel:
    """Mock-driveren skal speile press()/release() i read()."""

    def test_alle_knapper_utlost_ved_oppstart(self):
        btns = MockButtons()
        assert btns.read() == 0

    def test_press_setter_riktig_bit(self):
        btns = MockButtons()
        btns.press(2)
        assert btns.read() == 0b00100

    def test_release_klarer_bit(self):
        btns = MockButtons()
        btns.press(0)
        btns.press(4)
        assert btns.read() == 0b10001
        btns.release(0)
        assert btns.read() == 0b10000

    def test_set_state_overstyrer_helt(self):
        btns = MockButtons()
        btns.press(0)
        btns.set_state(0b11111)
        assert btns.read() == 0b11111

    def test_set_state_maskerer_overflodige_bits(self):
        btns = MockButtons()
        btns.set_state(0xFF)
        assert btns.read() == 0b11111

    def test_press_med_ugyldig_indeks_kaster(self):
        btns = MockButtons()
        with pytest.raises(ValueError):
            btns.press(5)
        with pytest.raises(ValueError):
            btns.press(-1)

    def test_close_idempotent(self):
        btns = MockButtons()
        btns.close()
        btns.close()  # skal ikke kaste

    def test_traadtrygg(self):
        """press()/release() fra mange tråder samtidig."""
        btns = MockButtons()
        n_iters = 200

        def hammer(idx: int):
            for _ in range(n_iters):
                btns.press(idx)
                btns.release(idx)

        threads = [threading.Thread(target=hammer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Alle skal være sluppet til slutt
        assert btns.read() == 0


class _FakeBus:
    """I2C-bus-stubb som returnerer en gitt byte. Brukes til å
    teste AttinyI2CButtons uten ekte hardware."""

    def __init__(self, value: int) -> None:
        self.value = value
        self.calls = []

    def read_byte(self, address: int) -> int:
        self.calls.append(address)
        return self.value


class TestAttinyI2CButtons:
    """Verifiser bit-maskering og adresse-bruk for ATTINY-driveren."""

    def test_default_mapping_speiler_byte(self):
        bus = _FakeBus(0b00010101)  # bit 0, 2, 4 satt
        drv = AttinyI2CButtons(bus, address=0x20)
        assert drv.read() == 0b10101

    def test_alle_knapper_trykket(self):
        bus = _FakeBus(0b00011111)
        drv = AttinyI2CButtons(bus)
        assert drv.read() == 0b11111

    def test_uvedkommende_bits_filtreres_bort(self):
        # Bit 5, 6, 7 er ikke knapper og skal ignoreres
        bus = _FakeBus(0b11100000)
        drv = AttinyI2CButtons(bus)
        assert drv.read() == 0

    def test_bus_kalles_med_riktig_adresse(self):
        bus = _FakeBus(0)
        drv = AttinyI2CButtons(bus, address=0x42)
        drv.read()
        assert bus.calls == [0x42]

    def test_egendefinert_button_bits_remapper(self):
        # Hvis ATTINY skulle legge bit 7 = knapp 1, bit 6 = knapp 2, …
        bus = _FakeBus(0b10000000)
        drv = AttinyI2CButtons(bus, button_bits=[7, 6, 5, 4, 3])
        # Bit 7 satt -> knapp 1 -> bit 0 i resultat
        assert drv.read() == 0b00001

    def test_feil_lengde_button_bits_kaster(self):
        bus = _FakeBus(0)
        with pytest.raises(ValueError):
            AttinyI2CButtons(bus, button_bits=[0, 1, 2])

    def test_ugyldig_bit_indeks_kaster(self):
        bus = _FakeBus(0)
        with pytest.raises(ValueError):
            AttinyI2CButtons(bus, button_bits=[0, 1, 2, 3, 8])

    def test_close_er_idempotent(self):
        drv = AttinyI2CButtons(_FakeBus(0))
        drv.close()
        drv.close()


class TestRPiGPIOButtonsValidering:
    """Begrenset test — full GPIO-test krever RPi-hardware."""

    def test_feil_antall_pinner_kaster(self):
        # Importeres lokalt for å unngå gpiozero-import når testen
        # bare sjekker validering
        from stewart_platform.hardware.rpi_gpio_buttons import RPiGPIOButtons

        with pytest.raises(ValueError):
            RPiGPIOButtons([17, 27, 22])
