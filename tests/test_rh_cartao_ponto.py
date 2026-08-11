from datetime import datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domain.entities.rh import RegistroPonto, StatusPonto, TipoPonto
from app.domain.services.rh_cartao_ponto import LinhaCartao, montar_linha

TZ = ZoneInfo("America/Sao_Paulo")


def _reg(hora_utc: int, minuto_utc: int, tipo: TipoPonto, status=StatusPonto.VALIDADO):
    return RegistroPonto(
        team_id=uuid4(),
        funcionario_id=uuid4(),
        tipo=tipo,
        timestamp=datetime(2026, 8, 10, hora_utc, minuto_utc, tzinfo=timezone.utc),
        latitude=0.0,
        longitude=0.0,
        status=status,
    )


def test_dia_completo_preenche_as_quatro_colunas():
    # 08:00, 12:00, 13:00 e 17:48 locais.
    registros = [
        _reg(11, 0, TipoPonto.ENTRADA),
        _reg(15, 0, TipoPonto.SAIDA),
        _reg(16, 0, TipoPonto.ENTRADA),
        _reg(20, 48, TipoPonto.SAIDA),
    ]
    assert montar_linha(registros, TZ) == LinhaCartao(
        entrada=time(8, 0),
        saida_intervalo=time(12, 0),
        retorno_intervalo=time(13, 0),
        saida=time(17, 48),
    )


def test_dia_com_duas_batidas_preenche_apenas_entrada_e_saida():
    registros = [_reg(11, 0, TipoPonto.ENTRADA), _reg(20, 48, TipoPonto.SAIDA)]
    assert montar_linha(registros, TZ) == LinhaCartao(
        entrada=time(8, 0),
        saida_intervalo=None,
        retorno_intervalo=None,
        saida=time(17, 48),
    )


def test_dia_com_batidas_impares_fica_vazio():
    registros = [
        _reg(11, 0, TipoPonto.ENTRADA),
        _reg(15, 0, TipoPonto.SAIDA),
        _reg(16, 0, TipoPonto.ENTRADA),
    ]
    assert montar_linha(registros, TZ) == LinhaCartao(None, None, None, None)


def test_dia_sem_batidas_fica_vazio():
    assert montar_linha([], TZ) == LinhaCartao(None, None, None, None)


def test_ignora_registros_negados():
    registros = [
        _reg(11, 0, TipoPonto.ENTRADA),
        _reg(12, 0, TipoPonto.SAIDA, status=StatusPonto.NEGADO),
        _reg(20, 48, TipoPonto.SAIDA),
    ]
    assert montar_linha(registros, TZ) == LinhaCartao(
        entrada=time(8, 0),
        saida_intervalo=None,
        retorno_intervalo=None,
        saida=time(17, 48),
    )


def test_registro_ajustado_conta_como_valido():
    registros = [
        _reg(11, 0, TipoPonto.ENTRADA, status=StatusPonto.AJUSTADO),
        _reg(20, 48, TipoPonto.SAIDA, status=StatusPonto.AJUSTADO),
    ]
    assert montar_linha(registros, TZ).entrada == time(8, 0)


def test_batida_noturna_usa_hora_de_parede_local():
    # 21:00 UTC do dia 10 e 18:00 local; 02:00 UTC do dia 11 e 23:00 local do dia 10.
    registros = [
        RegistroPonto(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            tipo=TipoPonto.ENTRADA,
            timestamp=datetime(2026, 8, 10, 21, 0, tzinfo=timezone.utc),
            latitude=0.0,
            longitude=0.0,
            status=StatusPonto.VALIDADO,
        ),
        RegistroPonto(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            tipo=TipoPonto.SAIDA,
            timestamp=datetime(2026, 8, 11, 2, 0, tzinfo=timezone.utc),
            latitude=0.0,
            longitude=0.0,
            status=StatusPonto.VALIDADO,
        ),
    ]
    linha = montar_linha(registros, TZ)
    assert linha.entrada == time(18, 0)
    assert linha.saida == time(23, 0)
