# pid_controller.py
# =================
# PID-regulator for en enkelt akse.
# Implementerer en standard PID-algoritme med anti-windup
# for integraldelen. 6 instanser brukes av PoseController
# (en per frihetsgrad: X, Y, Z, roll, pitch, yaw).

from __future__ import annotations

from ..config.platform_config import PIDGains


class PIDController:
    """PID-regulator for en enkelt kontrollakse.

    Implementerer en diskret PID-algoritme med:
    - Proporsjonalledd (P): Reagerer på nåværende feil.
    - Integralledd (I): Eliminerer stasjonær feil over tid.
    - Derivatledd (D): Demper svingninger.
    - Anti-windup: Begrenser integralleddet for å unngå oppsamling.
    - Utgangsbegrensning: Klemmer utgangsverdi til [output_min, output_max].

    Alle forsterkningsparametre kan justeres via PIDGains-konfigurasjon.
    """

    def __init__(self, gains: PIDGains) -> None:
        """Opprett en ny PID-regulator.

        Args:
            gains: Forsterkning og begrensninger for regulatoren.
        """
        self._gains = gains
        self._integral = 0.0
        self._previous_error = 0.0

    def update(self, setpoint: float, measurement: float, dt: float) -> float:
        """Beregn PID-utgangen for en kontrollsyklus.

        Kalles en gang per kontrollsløyfe-iterasjon med det ønskede
        setpunktet og den målte verdien. Returnerer en korreksjon
        som skal brukes til å justere styresignalet.

        Args:
            setpoint: Ønsket målverdi.
            measurement: Faktisk målt verdi.
            dt: Tid siden forrige oppdatering i sekunder.

        Returns:
            Korreksjonsverdi begrenset til [output_min, output_max].
        """
        error = setpoint - measurement

        # Proporsjonalledd
        p_term = self._gains.kp * error

        # Integralledd med anti-windup
        self._integral += error * dt
        self._integral = max(-self._gains.integral_limit,
                             min(self._gains.integral_limit, self._integral))
        i_term = self._gains.ki * self._integral

        # Derivatledd
        d_term = self._gains.kd * (error - self._previous_error) / dt if dt > 0 else 0.0
        self._previous_error = error

        # Sum med utgangsbegrensning
        output = p_term + i_term + d_term
        return max(self._gains.output_min, min(self._gains.output_max, output))

    def reset(self) -> None:
        """Nullstill regulatorens interne tilstand.

        Setter integral og forrige feil til 0. Bør kalles
        ved oppstart eller etter nødstopp for å unngå
        uventede utslag fra gammelt integralbidrag.
        """
        self._integral = 0.0
        self._previous_error = 0.0

    def set_gains(self, gains: PIDGains) -> None:
        """Oppdater forsterkningsparametrene.

        Tillater sanntidsjustering av PID-parametere uten å
        opprette en ny regulator. Integral og derivattilstand
        beholdes.

        Args:
            gains: Nye PID-forsterkningsverdier.
        """
        self._gains = gains
