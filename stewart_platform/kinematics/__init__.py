# kinematics
# ==========
# Kinematikkpakke for Stewart-plattformen.
# Inneholder invers kinematikk-solver som beregner de 6
# servovinklene som trengs for å oppnå en ønsket rotasjonspose.

from .inverse_kinematics import InverseKinematics

__all__ = ["InverseKinematics"]
