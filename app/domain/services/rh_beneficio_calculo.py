from __future__ import annotations

import calendar
from datetime import date

from app.domain.entities.money import Money


def _dias_uteis_do_mes(mes: int, ano: int) -> list[date]:
    _, total = calendar.monthrange(ano, mes)
    dias = []
    for dia in range(1, total + 1):
        d = date(ano, mes, dia)
        if d.weekday() < 5:  # 0=Mon ... 4=Fri
            dias.append(d)
    return dias


def dias_uteis_competencia(mes: int, ano: int) -> int:
    return len(_dias_uteis_do_mes(mes, ano))


def contar_faltas(mes: int, ano: int, dias_presenca: set[date]) -> int:
    dias_uteis = _dias_uteis_do_mes(mes, ano)
    return sum(1 for d in dias_uteis if d not in dias_presenca)


def valor_beneficio(valor_dia: Money, dias_uteis: int, faltas: int) -> Money:
    dias_pagos = max(0, dias_uteis - faltas)
    return valor_dia * dias_pagos
