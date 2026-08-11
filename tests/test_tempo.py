from datetime import date, datetime, time, timezone

from app.core.tempo import (
    combine_local,
    day_bounds,
    local_date_of,
    local_time_of,
    to_local,
)


def test_local_date_of_mantem_batida_noturna_no_dia_local():
    # 2026-08-10 23:30 em Sao Paulo equivale a 2026-08-11 02:30 UTC.
    # Agrupando em UTC essa batida cairia no dia 11, que e o bug.
    instante = datetime(2026, 8, 11, 2, 30, tzinfo=timezone.utc)
    assert local_date_of(instante) == date(2026, 8, 10)


def test_local_date_of_trata_naive_como_utc():
    assert local_date_of(datetime(2026, 8, 11, 2, 30)) == date(2026, 8, 10)


def test_to_local_converte_para_menos_tres():
    instante = datetime(2026, 8, 10, 20, 48, tzinfo=timezone.utc)
    assert to_local(instante).hour == 17
    assert to_local(instante).minute == 48


def test_local_time_of_devolve_hora_de_parede():
    instante = datetime(2026, 8, 10, 20, 48, tzinfo=timezone.utc)
    assert local_time_of(instante) == time(17, 48)


def test_day_bounds_cobre_o_dia_local_inteiro_em_utc():
    start, end = day_bounds(date(2026, 8, 10))
    assert start == datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
    assert end.replace(microsecond=0) == datetime(2026, 8, 11, 2, 59, 59, tzinfo=timezone.utc)


def test_combine_local_converte_hora_de_parede_para_utc():
    # O caso da reclamacao: saida as 17:48 do dia 10.
    assert combine_local(date(2026, 8, 10), time(17, 48)) == datetime(
        2026, 8, 10, 20, 48, tzinfo=timezone.utc
    )
