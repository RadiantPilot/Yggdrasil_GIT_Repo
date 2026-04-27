# button_interface.py
# ===================
# Abstrakt grensesnitt for det fysiske 5-knappers navigasjonskortet.
# Konkrete implementasjoner kan lese knappene direkte fra GPIO eller
# via en ATTINY1624 over I2C — eller fra en mock-driver under tester.
# Dette gjør det mulig å bytte tilkoblingsmåte uten å endre GUI-laget.

from __future__ import annotations

from abc import ABC, abstractmethod


class ButtonInterface(ABC):
    """Abstrakt baseklasse for det fysiske knappekortet.

    Alle konkrete drivere (RPiGPIOButtons, AttinyI2CButtons, MockButtons)
    må implementere read() som returnerer en bitmaske der bit i er satt
    hvis knapp i (0..4) er trykket. Kontrakten er bevisst minimal — all
    debouncing og tilstandstracking håndteres av ButtonWorker.
    """

    # Antall knapper som forventes på kortet (1..5 -> bit 0..4).
    NUM_BUTTONS = 5

    @abstractmethod
    def read(self) -> int:
        """Les nåværende knappestatus som bitmaske.

        Returns:
            Heltall der bit i (0..4) er 1 hvis knapp i+1 er trykket.
            Bit 0 = knapp 1 (venstre), bit 1 = knapp 2 (opp),
            bit 2 = knapp 3 (midt), bit 3 = knapp 4 (ned),
            bit 4 = knapp 5 (høyre).
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Frigjør ressurser knyttet til driveren.

        Skal kunne kalles flere ganger uten feil.
        """
        ...

    def __enter__(self) -> ButtonInterface:
        """Støtte for kontekstbehandling (with-blokk)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Lukk driveren automatisk ved avslutning av with-blokk."""
        self.close()
