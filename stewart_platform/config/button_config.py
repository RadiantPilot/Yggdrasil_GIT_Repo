# button_config.py
# ================
# Konfigurasjon for det fysiske knappekortet.
# Knappene kan kobles til RPi enten direkte via GPIO eller
# via en ATTINY1624 som serielliserer trykkene over I2C.
# Backend velges via "backend"-feltet i denne konfigen.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ButtonConfig:
    """Konfigurasjon for det 5-knappers navigasjonskortet.

    Knappene er fysisk plassert i et pluss-mønster:
        Knapp 1 = venstre, Knapp 2 = opp, Knapp 3 = midt,
        Knapp 4 = ned, Knapp 5 = høyre.

    Indekseringen 0..4 i koden følger samme rekkefølge som
    listene gpio_pins og i2c_button_bits, dvs. 0 = knapp 1.
    """

    # Skal knappene være aktive? Sett False for å deaktivere
    # hele input-systemet uten å fjerne config-blokken.
    enabled: bool = True

    # Hvilken backend som leser knappene:
    #   "gpio" — direkte fra RPi GPIO via gpiozero
    #   "i2c"  — via ATTINY1624 på I2C-bussen
    #   "mock" — for tester og GUI-utvikling uten hardware
    backend: str = "gpio"

    # Pollefrekvens for ButtonWorker i Hz.
    poll_hz: float = 50.0

    # Minimum tid en knapp må holdes stabil før den telles
    # som trykket eller sluppet (debouncing).
    debounce_ms: float = 20.0

    # Hvor lenge midt-knappen må holdes for å utløse E-STOP.
    long_press_ms: float = 1000.0

    # --- GPIO-backend ---
    # BCM-numre for de 5 knappene (knapp 1..5).
    # Standard tilsvarer pin 11, 13, 15, 19, 21 på RPi-headeren
    # = GPIO 17, 27, 22, 10, 9. Alle leses med intern pull-up.
    gpio_pins: List[int] = field(
        default_factory=lambda: [17, 27, 22, 10, 9]
    )

    # --- I2C-backend ---
    # I2C-adressen ATTINY-firmwaren responderer på.
    i2c_address: int = 0x20

    # Hvilken bit i den returnerte byten som svarer til hvilken
    # knapp. Default følger firmware/knappekort.ino: bit 0 = knapp 1,
    # …, bit 4 = knapp 5.
    i2c_button_bits: List[int] = field(
        default_factory=lambda: [0, 1, 2, 3, 4]
    )

    # --- Navigasjonsoppførsel ---
    # Steg for nudging i edit-mode. Brukes av Navigable-widgets
    # som ikke har sitt eget naturlige steg.
    nudge_steps: Dict[str, float] = field(
        default_factory=lambda: {
            "translation_mm": 1.0,
            "rotation_deg": 1.0,
            "pid_kp": 0.05,
            "pid_ki": 0.05,
            "pid_kd": 0.005,
        }
    )
