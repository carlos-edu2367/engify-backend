"""Calculo puro de parcelamento de pagamentos agendados.

Sem I/O e sem dependencia de repositorio — so aritmetica de valores e datas,
para poder ser testado isoladamente e reusado pelo servico.
"""
import calendar
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

MIN_PARCELAS = 2
MAX_PARCELAS = 36

_CENTAVO = Decimal("0.01")


def _validate_parcelas(parcelas: int) -> None:
    if parcelas < MIN_PARCELAS or parcelas > MAX_PARCELAS:
        raise ValueError(
            f"Numero de parcelas deve estar entre {MIN_PARCELAS} e {MAX_PARCELAS}"
        )


def split_valor_parcelas(total: Decimal, parcelas: int) -> list[Decimal]:
    """Divide ``total`` em ``parcelas`` valores que somam exatamente ``total``.

    As parcelas 1..N-1 recebem o valor base arredondado para baixo; a ultima
    absorve o residuo de centavos.
    """
    _validate_parcelas(parcelas)
    base = (total / Decimal(parcelas)).quantize(_CENTAVO, rounding=ROUND_DOWN)
    valores = [base] * (parcelas - 1)
    valores.append(total - base * (parcelas - 1))
    return valores


def _add_months(dt: datetime, months: int) -> datetime:
    """Avanca ``months`` meses preservando hora/tz, com clamp no ultimo dia do mes."""
    total = dt.month - 1 + months
    ano = dt.year + total // 12
    mes = total % 12 + 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return dt.replace(year=ano, month=mes, day=min(dt.day, ultimo_dia))


def build_datas_parcelas(primeira: datetime, parcelas: int) -> list[datetime]:
    """Gera ``parcelas`` vencimentos mensais a partir de ``primeira``."""
    _validate_parcelas(parcelas)
    return [_add_months(primeira, i) for i in range(parcelas)]
