# i2c_bus.py
# ==========
# Wrapper rundt smbus2.SMBus for I2C-kommunikasjon.
# Sentraliserer bussadministrasjon slik at bussnummer og
# feilhåndtering kun konfigureres ett sted. Støtter
# kontekstbehandling (with-blokk) for trygg ressursfrigivelse.

from __future__ import annotations

from typing import List


class I2CBus:
    """Abstraksjonslag for I2C-bussen på Raspberry Pi.

    Wrapper rundt smbus2.SMBus som gir ett enkelt tilgangspunkt
    for alle I2C-enheter. Bussnummeret konfigureres ved opprettelse
    og kan enkelt endres via PlatformConfig.

    Bruk som kontekstbehandler for automatisk lukking:
        with I2CBus(bus_number=1) as bus:
            bus.read_byte_data(0x40, 0x00)
    """

    def __init__(self, bus_number: int) -> None:
        """Opprett en ny I2C-bussforbindelse.

        Args:
            bus_number: I2C-bussnummer (vanligvis 1 på RPi 4B).
        """
        self._bus_number = bus_number
        # Lokal import slik at modulen kan importeres på dev-PC
        # uten smbus2 installert (kun feiler ved faktisk bruk).
        from smbus2 import SMBus
        self._bus = SMBus(bus_number)

    def read_byte(self, address: int) -> int:
        """Les en enkelt byte fra en I2C-enhet uten registeradresse.

        Brukes mot enheter som bare svarer på en ren read-transaksjon
        (start + addr+R + read + stop) — typisk slaves som er bygget
        rundt Arduino Wire.onRequest, slik som ATTINY-firmwaren på
        knappekortet. read_byte_data() ville sende en ekstra
        register-byte som disse slavene ikke har et konsept for.

        Args:
            address: I2C-adressen til enheten.

        Returns:
            Byteverdien som ble lest (0-255).
        """
        return self._bus.read_byte(address)

    def read_byte_data(self, address: int, register: int) -> int:
        """Les en enkelt byte fra et register på en I2C-enhet.

        Args:
            address: I2C-adressen til enheten (f.eks. 0x40).
            register: Registeradressen som skal leses.

        Returns:
            Byteverdien som ble lest (0-255).
        """
        return self._bus.read_byte_data(address, register)

    def write_byte_data(self, address: int, register: int, value: int) -> None:
        """Skriv en enkelt byte til et register på en I2C-enhet.

        Args:
            address: I2C-adressen til enheten.
            register: Registeradressen som skal skrives til.
            value: Byteverdien som skal skrives (0-255).
        """
        self._bus.write_byte_data(address, register, value)

    def read_block_data(self, address: int, register: int, length: int) -> List[int]:
        """Les en blokk med bytes fra en I2C-enhet.

        Nyttig for å lese flere sammenhengende registre i en
        operasjon, f.eks. akselerometerdata (6 bytes for X, Y, Z).

        Args:
            address: I2C-adressen til enheten.
            register: Startregisteradressen.
            length: Antall bytes som skal leses.

        Returns:
            Liste med byteverdier.
        """
        return list(self._bus.read_i2c_block_data(address, register, length))

    def write_block_data(self, address: int, register: int, data: List[int]) -> None:
        """Skriv en blokk med bytes til en I2C-enhet.

        Args:
            address: I2C-adressen til enheten.
            register: Startregisteradressen.
            data: Liste med byteverdier som skal skrives.
        """
        self._bus.write_i2c_block_data(address, register, list(data))

    def close(self) -> None:
        """Lukk I2C-bussforbindelsen og frigjør ressurser."""
        if self._bus is not None:
            self._bus.close()
            self._bus = None

    def __enter__(self) -> I2CBus:
        """Støtte for kontekstbehandling (with-blokk)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Lukk bussen automatisk ved avslutning av with-blokk."""
        self.close()
