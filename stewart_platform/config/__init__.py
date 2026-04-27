# config
# ======
# Konfigurasjonspakke for Stewart-plattformen.
# Samler alle justerbare parametere i dataklasser som kan
# serialiseres til/fra YAML for enkel justering uten kodeendringer.

from .button_config import ButtonConfig
from .platform_config import PlatformConfig, ServoConfig, PIDGains, SafetyConfig, Axis

__all__ = [
    "PlatformConfig",
    "ServoConfig",
    "PIDGains",
    "SafetyConfig",
    "Axis",
    "ButtonConfig",
]
