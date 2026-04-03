# test_control_pid_controller.py
# ===============================
# Tester for PIDController-klassen.
#
# PID-regulatoren er hjertet i tilbakekoblingsslofen. Den beregner
# en korreksjon basert pa avviket mellom onsket og malt verdi.
# 6 PID-regulatorer brukes (en per frihetsgrad) for a kontrollere
# plattformens posisjon og orientering.
#
# GUI-relevans:
#   GUI-en skal la brukeren justere kp, ki, kd i sanntid og se
#   effekten pa plattformens respons. Integral-tilstand og forrige
#   feil skal vaere tilgjengelig for visning/debugging.

import pytest

from stewart_platform.config.platform_config import PIDGains
from stewart_platform.control.pid_controller import PIDController


@pytest.fixture
def p_regulator():
    """Ren P-regulator (ki=0, kd=0) for enkle tester."""
    return PIDController(PIDGains(kp=1.0, ki=0.0, kd=0.0))


@pytest.fixture
def pid_regulator():
    """Komplett PID-regulator med alle tre ledd aktive."""
    return PIDController(PIDGains(kp=1.0, ki=0.5, kd=0.1))


class TestPIDOpprettelse:
    """Tester for opprettelse av PID-regulator."""

    def test_opprettelse(self):
        """Sjekk at en PID-regulator kan opprettes med PIDGains."""
        gains = PIDGains(kp=2.0, ki=0.1, kd=0.05)
        pid = PIDController(gains)
        assert pid is not None

    def test_startverdier_er_null(self):
        """Sjekk at integral og forrige feil starter pa null."""
        pid = PIDController(PIDGains())
        assert pid._integral == 0.0
        assert pid._previous_error == 0.0


class TestPIDProporsjonal:
    """Tester for proporsjonalleddet (P).

    P-leddet reagerer pa naavaerende feil: utgang = kp * error.
    """

    def test_ingen_feil_gir_null_utgang(self, p_regulator):
        """Sjekk at null feil (setpoint == measurement) gir null utgang.

        Nar plattformen er der den skal vaere, skal korreksjonen vaere 0.
        """
        result = p_regulator.update(setpoint=100.0, measurement=100.0, dt=0.02)
        assert result == pytest.approx(0.0)

    def test_positiv_feil_gir_positiv_utgang(self, p_regulator):
        """Sjekk at positiv feil (under setpunkt) gir positiv korreksjon.

        Nar maling er lavere enn setpunkt, skal regulatoren oke utgangen.
        """
        result = p_regulator.update(setpoint=100.0, measurement=90.0, dt=0.02)
        assert result > 0.0

    def test_negativ_feil_gir_negativ_utgang(self, p_regulator):
        """Sjekk at negativ feil (over setpunkt) gir negativ korreksjon."""
        result = p_regulator.update(setpoint=100.0, measurement=110.0, dt=0.02)
        assert result < 0.0

    def test_p_utgang_er_proporsjonal(self):
        """Sjekk at P-utgangen skalerer lineaert med kp.

        Dobling av kp skal doble utgangen for samme feil.
        """
        pid1 = PIDController(PIDGains(kp=1.0, ki=0.0, kd=0.0, output_min=-100.0, output_max=100.0))
        pid2 = PIDController(PIDGains(kp=2.0, ki=0.0, kd=0.0, output_min=-100.0, output_max=100.0))
        r1 = pid1.update(100.0, 90.0, 0.02)
        r2 = pid2.update(100.0, 90.0, 0.02)
        assert r2 == pytest.approx(r1 * 2.0)


class TestPIDIntegral:
    """Tester for integralleddet (I).

    I-leddet akkumulerer feil over tid for a eliminere stasjonaer feil.
    Anti-windup begrenser integralleddet for a unnga ustabilitet.
    """

    def test_integral_akkumulerer_over_tid(self):
        """Sjekk at gjentatte oppdateringer med samme feil oker utgangen.

        I-leddet bygger seg opp over tid for a eliminere konstant feil.
        """
        pid = PIDController(PIDGains(kp=0.0, ki=1.0, kd=0.0, output_min=-100.0, output_max=100.0))
        r1 = pid.update(100.0, 90.0, 0.02)  # feil = 10, integral += 10*0.02
        r2 = pid.update(100.0, 90.0, 0.02)  # feil = 10, integral += 10*0.02
        assert abs(r2) > abs(r1)

    def test_anti_windup(self):
        """Sjekk at integralet begrenses av integral_limit.

        Uten anti-windup kan integralet vokse uhemmet og forarsakke
        store oversving nar feilen endrer tegn.
        """
        pid = PIDController(PIDGains(
            kp=0.0, ki=1.0, kd=0.0,
            integral_limit=5.0,
            output_min=-1000.0, output_max=1000.0,
        ))
        # Kjor mange iterasjoner for a provere a akkumulere over grensen
        for _ in range(1000):
            pid.update(100.0, 0.0, 0.02)
        # Integralet skal vaere begrenset
        assert abs(pid._integral) <= 5.0


class TestPIDDerivat:
    """Tester for derivatleddet (D).

    D-leddet reagerer pa endringsraten til feilen for a dempe svingninger.
    """

    def test_konstant_feil_gir_null_d(self):
        """Sjekk at konstant feil (ingen endring) gir null D-bidrag.

        Nar feilen ikke endrer seg mellom iterasjoner, skal D-leddet
        ikke bidra noe.
        """
        pid = PIDController(PIDGains(kp=0.0, ki=0.0, kd=1.0, output_min=-100.0, output_max=100.0))
        pid.update(100.0, 90.0, 0.02)  # Forste kall setter forrige_feil
        result = pid.update(100.0, 90.0, 0.02)  # Samme feil
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_okende_feil_gir_positivt_d(self):
        """Sjekk at okende feil gir positivt D-bidrag.

        D-leddet skal forsterke korreksjonen nar feilen vokser.
        """
        pid = PIDController(PIDGains(kp=0.0, ki=0.0, kd=1.0, output_min=-100.0, output_max=100.0))
        pid.update(100.0, 95.0, 0.02)  # feil = 5
        result = pid.update(100.0, 90.0, 0.02)  # feil = 10, oker
        assert result > 0.0


class TestPIDUtgangsbegrensning:
    """Tester for begrensning av utgangsverdien.

    Utgangen klemmes mellom output_min og output_max for a
    beskytte servoene mot for store signaler.
    """

    def test_utgang_klemmes_til_max(self):
        """Sjekk at stor positiv feil gir utgang klemmet til output_max."""
        pid = PIDController(PIDGains(kp=100.0, output_min=-1.0, output_max=1.0))
        result = pid.update(100.0, 0.0, 0.02)
        assert result == pytest.approx(1.0)

    def test_utgang_klemmes_til_min(self):
        """Sjekk at stor negativ feil gir utgang klemmet til output_min."""
        pid = PIDController(PIDGains(kp=100.0, output_min=-1.0, output_max=1.0))
        result = pid.update(0.0, 100.0, 0.02)
        assert result == pytest.approx(-1.0)


class TestPIDReset:
    """Tester for nullstilling av regulator."""

    def test_reset_nullstiller_integral(self, pid_regulator):
        """Sjekk at reset() nullstiller integralleddet.

        Viktig etter nodstopp for a unnga uventet oppforsel.
        """
        pid_regulator.update(100.0, 90.0, 0.02)
        pid_regulator.update(100.0, 90.0, 0.02)
        pid_regulator.reset()
        assert pid_regulator._integral == 0.0
        assert pid_regulator._previous_error == 0.0


class TestPIDSetGains:
    """Tester for justering av PID-parametere under kjoring.

    GUI-en bruker set_gains() for a la brukeren tune PID i sanntid.
    """

    def test_set_gains_oppdaterer(self):
        """Sjekk at set_gains() oppdaterer forsterkningsverdiene."""
        pid = PIDController(PIDGains(kp=1.0))
        nye_gains = PIDGains(kp=3.0, ki=0.2, kd=0.05)
        pid.set_gains(nye_gains)
        assert pid._gains.kp == 3.0
        assert pid._gains.ki == 0.2
        assert pid._gains.kd == 0.05
