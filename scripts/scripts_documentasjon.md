# Scripts

Hjelpeskript for hardware-bringup, kalibrering og manuell testing.

---

| Script | Hva det gjør |
|---|---|
| `bringup_imu.py` | Sjekker at LSM6DSOXTR IMU svarer på I2C og leverer fornuftige målinger. Ingen servobevegelse. |
| `bringup_pca9685.py` | Sjekker at PCA9685 PWM-driveren svarer på I2C og at register-skriving fungerer. Sender én midt-puls (1500 µs) til kanal 0, slår av igjen. |
| `bringup_one_servo.py` | Sender manuelle pulsbredder til én servo (default kanal 0) med pause mellom hvert steg. Brukes til å bekrefte retning og mekanisk bevegelse. |
| `sweep_all_servos.py` | Sweeper alle 6 servoer fram og tilbake mellom to pulsbredder, kontinuerlig til Ctrl+C. Rå PWM — ingen config-lasting. |
| `home_all_servos.py` | Vrir hver servo litt og setter deretter alle til hjemmeposisjon. Brukes som oppvarming før hovedkoden startes. |
| `check_home_geometry.py` | Regner ut IK-vinkler for `Pose.home()` og viser hvor mye `home_height` bør justeres. Ingen hardware-avhengighet. |
| `test_servo_sweep.py` | Interaktiv test: velg servo 1–6, og den beveger seg jevnt fra bunn til topp og tilbake til midt. Gjentas til Ctrl+C. |

---

Alle script kjøres fra rotkatalogen:

```
python scripts/<script>.py
python scripts/<script>.py --help   # vis tilgjengelige flagg
```
