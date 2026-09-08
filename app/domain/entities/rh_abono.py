from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from app.domain.errors import DomainError

_MOTIVO_MAX_LEN = 255


class AbonoFalta:
    def __init__(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        data: date,
        motivo: str,
        created_by_user_id: UUID | None = None,
        id: UUID | None = None,
        is_deleted: bool = False,
    ) -> None:
        motivo = motivo.strip()
        if not motivo:
            raise DomainError("Motivo do abono e obrigatorio")
        if len(motivo) > _MOTIVO_MAX_LEN:
            raise DomainError(f"Motivo do abono deve ter no maximo {_MOTIVO_MAX_LEN} caracteres")
        self.id = id or uuid4()
        self.team_id = team_id
        self.funcionario_id = funcionario_id
        self.data = data
        self.motivo = motivo
        self.created_by_user_id = created_by_user_id
        self.is_deleted = is_deleted

    def revogar(self) -> None:
        self.is_deleted = True
