# servo
# =====
# Servomotorstyringspakke.
# Håndterer individuell servokontroll med vinkel-til-puls-konvertering,
# retning, grenser og kalibreringsoffset, samt batchoperasjoner
# for alle 6 servoer via ServoArray.

from .servo import Servo
from .servo_array import ServoArray

__all__ = ["Servo", "ServoArray"]
