from __future__ import annotations

from datetime import date
from datetime import time as Time
from enum import Enum
from uuid import UUID, uuid4

from app.domain.errors import DomainError


class TipoEventoCalendario(Enum):
    FERIADO = "feriado"
    PONTO_FACULTATIVO = "ponto_facultativo"
    ABONO = "abono"
    LIBERACAO_ANTECIPADA = "liberacao_antecipada"


class EventoCalendarioRh:
    def __init__(
        self,
        team_id: UUID,
        tipo: TipoEventoCalendario,
        data: date,
        descricao: str,
        hora_corte: Time | None = None,
        aplica_todos: bool = True,
        funcionario_ids: list[UUID] | None = None,
        id: UUID | None = None,
    ) -> None:
        if not descricao.strip():
            raise DomainError("Descricao do evento de calendario e obrigatoria")
        if tipo == TipoEventoCalendario.LIBERACAO_ANTECIPADA and hora_corte is None:
            raise DomainError("Liberacao antecipada exige hora de corte")
        if tipo != TipoEventoCalendario.LIBERACAO_ANTECIPADA and hora_corte is not None:
            raise DomainError("Somente liberacao antecipada usa hora de corte")
        if not aplica_todos and not funcionario_ids:
            raise DomainError("Informe ao menos um funcionario quando o evento nao se aplica a todos")
        self.id = id or uuid4()
        self.team_id = team_id
        self.tipo = tipo
        self.data = data
        self.descricao = descricao
        self.hora_corte = hora_corte
        self.aplica_todos = aplica_todos
        self.funcionario_ids = list(funcionario_ids or [])
        self.is_deleted = False

    def aplica_a(self, funcionario_id: UUID) -> bool:
        return self.aplica_todos or funcionario_id in self.funcionario_ids

    def delete(self) -> None:
        self.is_deleted = True
