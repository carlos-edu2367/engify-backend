from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.money import Money
from app.domain.entities.rh import (
    IntervaloHorario,
    RegistroPonto,
    StatusPonto,
    TipoPonto,
    TurnoHorario,
)
from app.domain.services.rh_ponto_calculo import (
    JornadaConfig,
    resultado_dia,
    valor_minuto,
    valor_hora_extra,
)


def _turno_8h():
    # 08:00-17:00 com 1h de intervalo => 8h esperadas
    return TurnoHorario(
        dia_semana=0,
        hora_entrada=time(8, 0),
        hora_saida=time(17, 0),
        intervalos=[IntervaloHorario(time(12, 0), time(13, 0))],
    )


def _reg(hora: time, tipo: TipoPonto, status: StatusPonto = StatusPonto.VALIDADO):
    return RegistroPonto(
        team_id=uuid4(),
        funcionario_id=uuid4(),
        tipo=tipo,
        timestamp=datetime.combine(datetime(2026, 7, 6).date(), hora, tzinfo=timezone.utc),
        latitude=0.0,
        longitude=0.0,
        status=status,
    )


def test_jornada_config_defaults():
    config = JornadaConfig()
    assert config.divisor_mensal_horas == Decimal("220")
    assert config.adicional_extra_percentual == Decimal("50")


def test_valor_minuto_usa_divisor_fixo():
    # 220h * 60 = 13.200 minutos; 2200 / 13200 = 0.1666... (Decimal cru, sem quantizar)
    salario = Money(Decimal("2200.00"))
    minuto = valor_minuto(salario, JornadaConfig())
    assert minuto.quantize(Decimal("0.0001")) == Decimal("0.1667")


def test_valor_hora_extra_aplica_adicional():
    salario = Money(Decimal("2200.00"))
    config = JornadaConfig(adicional_extra_percentual=Decimal("50"))
    # valor do minuto normal * 1.5, por 60 minutos
    extra_hora = valor_hora_extra(salario, Decimal("60"), config)
    esperado = (Decimal("2200.00") / Decimal("13200")) * Decimal("1.5") * Decimal("60")
    assert extra_hora.amount == esperado.quantize(Decimal("0.01"))


def test_dia_completo_sem_extra_nem_falta():
    turno = _turno_8h()
    registros = [_reg(time(8, 0), TipoPonto.ENTRADA), _reg(time(17, 0), TipoPonto.SAIDA)]
    r = resultado_dia(registros, turno)
    assert r.trabalhado_min == Decimal("480")  # 9h span - 1h intervalo
    assert r.extra_min == Decimal("0")
    assert r.falta_min == Decimal("0")
    assert r.incompleto is False


def test_almoco_batido_nao_desconta_em_dobro():
    turno = _turno_8h()
    # bate saida/volta do almoco: span continua 08:00->17:00, intervalo fixo desconta 1x
    registros = [
        _reg(time(8, 0), TipoPonto.ENTRADA),
        _reg(time(12, 0), TipoPonto.SAIDA),
        _reg(time(13, 0), TipoPonto.ENTRADA),
        _reg(time(17, 0), TipoPonto.SAIDA),
    ]
    r = resultado_dia(registros, turno)
    assert r.trabalhado_min == Decimal("480")  # NAO 420


def test_saida_antecipada_gera_falta_parcial():
    turno = _turno_8h()
    registros = [_reg(time(8, 0), TipoPonto.ENTRADA), _reg(time(15, 0), TipoPonto.SAIDA)]
    r = resultado_dia(registros, turno)
    # span 7h - 1h intervalo = 6h trabalhadas; esperado 8h => 2h falta
    assert r.trabalhado_min == Decimal("360")
    assert r.falta_min == Decimal("120")
    assert r.extra_min == Decimal("0")


def test_hora_extra():
    turno = _turno_8h()
    registros = [_reg(time(8, 0), TipoPonto.ENTRADA), _reg(time(19, 0), TipoPonto.SAIDA)]
    r = resultado_dia(registros, turno)
    # span 11h - 1h = 10h; esperado 8h => 2h extra
    assert r.extra_min == Decimal("120")
    assert r.falta_min == Decimal("0")


def test_ausencia_total_e_falta_cheia():
    turno = _turno_8h()
    r = resultado_dia([], turno)
    assert r.falta_min == Decimal("480")
    assert r.incompleto is False


def test_ponto_esquecido_marca_incompleto_sem_descontar():
    turno = _turno_8h()
    registros = [_reg(time(8, 0), TipoPonto.ENTRADA)]  # esqueceu a saida
    r = resultado_dia(registros, turno)
    assert r.incompleto is True
    assert r.falta_min == Decimal("0")
    assert r.extra_min == Decimal("0")


def test_ignora_status_negado_ou_inconsistente():
    turno = _turno_8h()
    registros = [
        _reg(time(8, 0), TipoPonto.ENTRADA),
        _reg(time(9, 0), TipoPonto.SAIDA, status=StatusPonto.NEGADO),
        _reg(time(17, 0), TipoPonto.SAIDA),
    ]
    r = resultado_dia(registros, turno)
    # negado ignorado -> par valido = 08:00/17:00
    assert r.trabalhado_min == Decimal("480")
    assert r.incompleto is False
