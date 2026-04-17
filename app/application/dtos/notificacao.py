from dataclasses import dataclass
from uuid import UUID
from app.domain.entities.notificacao import TipoNotificacao


@dataclass
class CreateNotificacaoDTO:
    user_id: UUID
    team_id: UUID
    tipo: TipoNotificacao
    titulo: str
    mensagem: str
    reference_id: UUID | None = None
