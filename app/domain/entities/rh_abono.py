from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID, uuid4

from app.domain.errors import DomainError

_MOTIVO_MAX_LEN = 255
_MINUTOS_MAX = 24 * 60


class AbonoFalta:
    """Abono lancado pelo RH para um dia de um funcionario.

    Sem `minutos`, abona o dia inteiro. Com `minutos`, perdoa so parte das
    horas devidas naquele dia (ex.: saiu 1h30 antes para uma consulta).
    """

    def __init__(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        data: date,
        motivo: str,
        created_by_user_id: UUID | None = None,
        id: UUID | None = None,
        is_deleted: bool = False,
        minutos: int | None = None,
    ) -> None:
        motivo = motivo.strip()
        if not motivo:
            raise DomainError("Motivo do abono e obrigatorio")
        if len(motivo) > _MOTIVO_MAX_LEN:
            raise DomainError(f"Motivo do abono deve ter no maximo {_MOTIVO_MAX_LEN} caracteres")
        if minutos is not None and not 1 <= minutos <= _MINUTOS_MAX:
            raise DomainError(f"Horas abonadas devem ficar entre 1 minuto e {_MINUTOS_MAX // 60} horas")
        self.id = id or uuid4()
        self.team_id = team_id
        self.funcionario_id = funcionario_id
        self.data = data
        self.motivo = motivo
        self.created_by_user_id = created_by_user_id
        self.is_deleted = is_deleted
        self.minutos = minutos

    @property
    def dia_inteiro(self) -> bool:
        return self.minutos is None

    def revogar(self) -> None:
        self.is_deleted = True


def separar_abonos(
    abonos: Iterable[AbonoFalta],
) -> tuple[dict[UUID, set[date]], dict[UUID, dict[date, Decimal]]]:
    """Separa abonos de dia inteiro dos parciais, por funcionario.

    Dia inteiro vira data abonada. Parciais do mesmo dia se somam: o RH pode
    abonar 1h agora e mais 30min depois, e o calculo limita o total a divida
    do dia, entao abonar a mais nunca vira credito de horas.
    """
    datas: dict[UUID, set[date]] = defaultdict(set)
    minutos: dict[UUID, dict[date, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for abono in abonos:
        if abono.minutos is None:
            datas[abono.funcionario_id].add(abono.data)
        else:
            minutos[abono.funcionario_id][abono.data] += Decimal(abono.minutos)
    return dict(datas), {funcionario_id: dict(por_dia) for funcionario_id, por_dia in minutos.items()}
