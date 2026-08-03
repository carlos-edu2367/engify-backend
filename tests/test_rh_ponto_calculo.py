from datetime import date, datetime, time, timezone
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
    minutos_liberacao,
    resultado_dia,
    resumir_periodo,
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


def test_resumir_periodo_soma_extra_falta_incompleto():
    turno = _turno_8h()  # apenas segunda (dia_semana=0)

    def turno_para_dia(weekday: int):
        return turno if weekday == 0 else None

    # 2026-07-06 e' segunda. Cria um dia com 2h extra.
    registros = [_reg(time(8, 0), TipoPonto.ENTRADA), _reg(time(19, 0), TipoPonto.SAIDA)]
    resumo = resumir_periodo(
        registros=registros,
        turno_para_dia=turno_para_dia,
        inicio=date(2026, 7, 6),
        fim=date(2026, 7, 6),
        datas_abonadas=set(),
    )
    assert resumo.extra_min == Decimal("120")
    assert resumo.falta_min == Decimal("0")
    assert resumo.faltas == 0
    assert resumo.dias_incompletos == 0


def test_resumir_periodo_pula_datas_abonadas():
    turno = _turno_8h()

    def turno_para_dia(weekday: int):
        return turno if weekday == 0 else None

    resumo = resumir_periodo(
        registros=[],  # sem batidas
        turno_para_dia=turno_para_dia,
        inicio=date(2026, 7, 6),
        fim=date(2026, 7, 6),
        datas_abonadas={date(2026, 7, 6)},
    )
    # dia abonado nao vira falta
    assert resumo.faltas == 0
    assert resumo.falta_min == Decimal("0")


def test_liberacao_antecipada_reduz_esperado_e_evita_falta():
    turno = _turno_8h()  # apenas segunda (dia_semana=0)

    def turno_para_dia(weekday: int):
        return turno if weekday == 0 else None

    # 2026-07-06 e segunda. Trabalha 08:00-15:00 (6h liquidas apos 1h de intervalo).
    registros = [_reg(time(8, 0), TipoPonto.ENTRADA), _reg(time(15, 0), TipoPonto.SAIDA)]
    resumo = resumir_periodo(
        registros=registros,
        turno_para_dia=turno_para_dia,
        inicio=date(2026, 7, 6),
        fim=date(2026, 7, 6),
        datas_abonadas=set(),
        liberacoes={date(2026, 7, 6): Decimal("360")},
    )
    assert resumo.falta_min == Decimal("0")
    assert resumo.extra_min == Decimal("0")
    assert resumo.esperado_min == Decimal("360")


def test_sem_liberacao_mesmo_horario_gera_falta_parcial():
    turno = _turno_8h()

    def turno_para_dia(weekday: int):
        return turno if weekday == 0 else None

    registros = [_reg(time(8, 0), TipoPonto.ENTRADA), _reg(time(15, 0), TipoPonto.SAIDA)]
    resumo = resumir_periodo(
        registros=registros,
        turno_para_dia=turno_para_dia,
        inicio=date(2026, 7, 6),
        fim=date(2026, 7, 6),
        datas_abonadas=set(),
    )
    assert resumo.falta_min == Decimal("120")


def test_minutos_liberacao_desconta_intervalo_sobreposto():
    turno = _turno_8h()  # 08-17, intervalo 12-13
    minutos = minutos_liberacao(turno, time(15, 0))
    assert minutos == Decimal("360")  # 08-15 = 7h, menos 1h de intervalo = 6h


def test_minutos_liberacao_corte_antes_da_entrada_retorna_zero():
    turno = _turno_8h()
    minutos = minutos_liberacao(turno, time(7, 0))
    assert minutos == Decimal("0")


def test_minutos_liberacao_corte_dentro_do_intervalo():
    turno = _turno_8h()
    minutos = minutos_liberacao(turno, time(12, 30))
    # bruto 08:00-12:30 = 270min; overlap com intervalo 12:00-13:00 clipado em 12:00-12:30 = 30min
    assert minutos == Decimal("240")


def test_resumir_periodo_classifica_dia_completo():
    from app.domain.services.rh_ponto_calculo import SituacaoDia

    turno = _turno_8h()
    dia = date(2026, 7, 6)
    registros = [_reg(time(8, 0), TipoPonto.ENTRADA), _reg(time(17, 0), TipoPonto.SAIDA)]

    resumo = resumir_periodo(
        registros=registros,
        turno_para_dia=lambda weekday: turno if weekday == 0 else None,
        inicio=dia,
        fim=dia,
        datas_abonadas=set(),
    )

    assert len(resumo.dias) == 1
    assert resumo.dias[0].data == dia
    assert resumo.dias[0].situacao == SituacaoDia.COMPLETO
    assert resumo.dias[0].esperado_min == Decimal("480")
    assert resumo.dias[0].trabalhado_min == Decimal("480")


def test_resumir_periodo_classifica_falta_parcial_e_extra():
    from app.domain.services.rh_ponto_calculo import SituacaoDia

    turno = _turno_8h()
    dia = date(2026, 7, 6)

    parcial = resumir_periodo(
        registros=[_reg(time(8, 0), TipoPonto.ENTRADA), _reg(time(15, 0), TipoPonto.SAIDA)],
        turno_para_dia=lambda weekday: turno if weekday == 0 else None,
        inicio=dia,
        fim=dia,
        datas_abonadas=set(),
    )
    assert parcial.dias[0].situacao == SituacaoDia.PARCIAL
    assert parcial.dias[0].falta_min == Decimal("120")

    extra = resumir_periodo(
        registros=[_reg(time(8, 0), TipoPonto.ENTRADA), _reg(time(18, 0), TipoPonto.SAIDA)],
        turno_para_dia=lambda weekday: turno if weekday == 0 else None,
        inicio=dia,
        fim=dia,
        datas_abonadas=set(),
    )
    assert extra.dias[0].situacao == SituacaoDia.EXTRA
    assert extra.dias[0].extra_min == Decimal("60")

    falta = resumir_periodo(
        registros=[],
        turno_para_dia=lambda weekday: turno if weekday == 0 else None,
        inicio=dia,
        fim=dia,
        datas_abonadas=set(),
    )
    assert falta.dias[0].situacao == SituacaoDia.FALTA
    assert falta.dias[0].falta_min == Decimal("480")


def test_resumir_periodo_classifica_batidas_impares_como_incompleto():
    from app.domain.services.rh_ponto_calculo import SituacaoDia

    turno = _turno_8h()
    dia = date(2026, 7, 6)

    resumo = resumir_periodo(
        registros=[_reg(time(8, 0), TipoPonto.ENTRADA)],
        turno_para_dia=lambda weekday: turno if weekday == 0 else None,
        inicio=dia,
        fim=dia,
        datas_abonadas=set(),
    )

    assert resumo.dias[0].situacao == SituacaoDia.INCOMPLETO
    assert resumo.dias_incompletos == 1


def test_resumir_periodo_marca_dia_sem_turno_como_sem_expediente():
    from app.domain.services.rh_ponto_calculo import SituacaoDia

    dia = date(2026, 7, 6)

    resumo = resumir_periodo(
        registros=[],
        turno_para_dia=lambda _weekday: None,
        inicio=dia,
        fim=dia,
        datas_abonadas=set(),
    )

    assert resumo.dias[0].situacao == SituacaoDia.SEM_EXPEDIENTE
    assert resumo.dias[0].esperado_min == Decimal("0")
    assert resumo.faltas == 0


def test_resumir_periodo_abonado_vence_a_classificacao_do_dia():
    from app.domain.services.rh_ponto_calculo import SituacaoDia

    turno = _turno_8h()
    dia = date(2026, 7, 6)

    resumo = resumir_periodo(
        registros=[_reg(time(8, 0), TipoPonto.ENTRADA), _reg(time(17, 0), TipoPonto.SAIDA)],
        turno_para_dia=lambda weekday: turno if weekday == 0 else None,
        inicio=dia,
        fim=dia,
        datas_abonadas={dia},
    )

    assert resumo.dias[0].situacao == SituacaoDia.ABONADO
    assert resumo.dias[0].esperado_min == Decimal("480")
    assert resumo.extra_min == Decimal("0")


def test_resumir_periodo_devolve_um_registro_por_dia_do_periodo():
    turno = _turno_8h()
    inicio = date(2026, 7, 6)
    fim = date(2026, 7, 12)

    resumo = resumir_periodo(
        registros=[],
        turno_para_dia=lambda weekday: turno if weekday == 0 else None,
        inicio=inicio,
        fim=fim,
        datas_abonadas=set(),
    )

    assert [d.data for d in resumo.dias] == [
        date(2026, 7, 6),
        date(2026, 7, 7),
        date(2026, 7, 8),
        date(2026, 7, 9),
        date(2026, 7, 10),
        date(2026, 7, 11),
        date(2026, 7, 12),
    ]
