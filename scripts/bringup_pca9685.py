# bringup_pca9685.py
# ==================
# Standalone hardware-bringup-test for PCA9685 PWM-driver.
# Verifiserer at brikken svarer på riktig adresse, kan resettes og
# konfigureres, og at vi kan skrive/lese kanal-registrene.
#
# Scriptet skriver et kort PWM-signal (1500 µs midt-puls) til kanal 0
# for å bekrefte at hele skrive-stien virker, men slår signalet av
# igjen før avslutning. Med ingen servoer tilkoblet er dette helt
# trygt — selv om det hadde vært en servo der, er 1500 µs midtstilling.
#
# Kjøres på Pi:
#     python scripts/bringup_pca9685.py

from __future__ import annotations

import sys
import time

from stewart_platform.hardware.i2c_bus import I2CBus
from stewart_platform.hardware.pca9685_driver import PCA9685Driver

I2C_BUS_NUMBER = 1
PCA_ADDRESS = 0x40
PWM_FREQUENCY_HZ = 50

# Register-adresser vi leser tilbake for å verifisere
_MODE1 = 0x00
_MODE2 = 0x01
_PRE_SCALE = 0xFE
_LED0_ON_L = 0x06   # Kanal 0: ON_L, ON_H, OFF_L, OFF_H ligger på 0x06..0x09

_OSCILLATOR_HZ = 25_000_000
_PWM_RESOLUTION = 4096


def main() -> int:
    bus = I2CBus(I2C_BUS_NUMBER)
    pca = PCA9685Driver(bus, address=PCA_ADDRESS, frequency=PWM_FREQUENCY_HZ)

    # --- Init -----------------------------------------------------------
    print(f"Initialiserer PCA9685 på 0x{PCA_ADDRESS:02X} med {PWM_FREQUENCY_HZ} Hz...")
    pca.reset()
    time.sleep(0.01)

    # --- Verifiser MODE1 ------------------------------------------------
    mode1 = bus.read_byte_data(PCA_ADDRESS, _MODE1)
    mode2 = bus.read_byte_data(PCA_ADDRESS, _MODE2)
    print(f"  MODE1 = 0x{mode1:02X}  (AI={bool(mode1 & 0x20)}, "
          f"SLEEP={bool(mode1 & 0x10)})")
    print(f"  MODE2 = 0x{mode2:02X}  (OUTDRV={bool(mode2 & 0x04)})")

    if mode1 & 0x10:
        print("  !! PCA9685 ligger fortsatt i SLEEP — ingen PWM vil komme ut")
        bus.close()
        return 1
    if not (mode1 & 0x20):
        print("  !! AUTO_INCREMENT ikke satt — blokk-skriving vil feile")
        bus.close()
        return 1

    # --- Verifiser frekvens via PRE_SCALE -------------------------------
    prescale = bus.read_byte_data(PCA_ADDRESS, _PRE_SCALE)
    expected = round(_OSCILLATOR_HZ / (_PWM_RESOLUTION * PWM_FREQUENCY_HZ)) - 1
    actual_freq = _OSCILLATOR_HZ / (_PWM_RESOLUTION * (prescale + 1))
    print(f"  PRE_SCALE = {prescale} (forventet {expected}) "
          f"-> faktisk frekvens ≈ {actual_freq:.1f} Hz")
    if prescale != expected:
        print("  !! Uventet PRE_SCALE — frekvens ikke satt riktig")
        bus.close()
        return 1

    # --- Skrive- og lese-test på kanal 0 --------------------------------
    print("\nSkriver 1500 µs (midtstilling) til kanal 0...")
    pca.set_pulse_width_us(0, 1500)
    time.sleep(0.01)

    data = bus.read_block_data(PCA_ADDRESS, _LED0_ON_L, 4)
    on = data[0] | (data[1] << 8)
    off = data[2] | (data[3] << 8)
    period_us = 1_000_000 / PWM_FREQUENCY_HZ
    pulse_us = off * period_us / _PWM_RESOLUTION
    print(f"  LED0 registre: ON={on}, OFF={off}  -> puls ≈ {pulse_us:.1f} µs")
    if not (1490 <= pulse_us <= 1510):
        print("  !! Pulsbredden avviker mer enn forventet")
        bus.close()
        return 1

    # --- Slå av alle kanaler igjen --------------------------------------
    print("\nSlår av alle PWM-kanaler...")
    pca.set_all_pwm(0, 0)
    time.sleep(0.01)
    data = bus.read_block_data(PCA_ADDRESS, _LED0_ON_L, 4)
    off_after = data[2] | (data[3] << 8)
    print(f"  LED0 OFF etter avslag = {off_after}  (forventet 0)")
    if off_after != 0:
        print("  !! Kanal 0 ble ikke nullstilt")
        bus.close()
        return 1

    bus.close()
    print("\nFerdig — PCA9685 svarer, er konfigurert, og kanal-registrene fungerer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
