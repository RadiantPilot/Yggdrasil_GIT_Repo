# stewart_platform
# ================
# Hovedpakke for Stewart-plattform kontrollsystem.
#
# Systemet styrer en 6-DOF Stewart-plattform via Raspberry Pi 4B.
# Arkitekturen er delt i følgende underpakker:
#   - config:      Konfigurasjon og justerbare parametere
#   - hardware:    Maskinvareabstraksjon (I2C, PWM, IMU)
#   - geometry:    3D-geometri, poser og plattformgeometri
#   - servo:       Servomotorstyring
#   - kinematics:  Invers kinematikk
#   - control:     Bevegelseskontroll og PID-regulering
#   - safety:      Sikkerhetsovervåking og nødstopp
