"""Traduz as batidas de um dia nas quatro colunas do cartao de ponto.

Mesma regra ja usada na tela do RH (punchClassification.ts): ordena as
batidas validas do dia, e a primeira e entrada, a ultima e saida, e as do
meio sao o intervalo. Numero impar de batidas significa dia inconclusivo —
o cartao sai em branco para ser preenchido a mao, em vez de exibir um
horario que o sistema nao consegue afirmar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time as Time, tzinfo

from app.domain.entities.rh import RegistroPonto, StatusPonto, TipoPonto

_STATUS_VALIDOS = {StatusPonto.VALIDADO, StatusPonto.AJUSTADO}


@dataclass(frozen=True)
class LinhaCartao:
    entrada: Time | None
    saida_intervalo: Time | None
    retorno_intervalo: Time | None
    saida: Time | None


def montar_linha(registros: list[RegistroPonto], tz: tzinfo) -> LinhaCartao:
    validos = sorted(
        [r for r in registros if r.status in _STATUS_VALIDOS and not r.is_deleted],
        key=lambda r: r.timestamp,
    )
    if len(validos) < 2 or len(validos) % 2 != 0:
        return LinhaCartao(None, None, None, None)

    def hora(registro: RegistroPonto) -> Time:
        return registro.timestamp.astimezone(tz).time().replace(second=0, microsecond=0)

    miolo = validos[1:-1]
    saida_intervalo = next((hora(r) for r in miolo if r.tipo == TipoPonto.SAIDA), None)
    retorno_intervalo = next((hora(r) for r in miolo if r.tipo == TipoPonto.ENTRADA), None)

    return LinhaCartao(
        entrada=hora(validos[0]),
        saida_intervalo=saida_intervalo,
        retorno_intervalo=retorno_intervalo,
        saida=hora(validos[-1]),
    )
