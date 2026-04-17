from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime, timezone


class TipoNotificacao(Enum):
    MENCAO_MURAL = "mencao_mural"
    PRAZO_7_DIAS = "prazo_7_dias"
    PRAZO_1_DIA = "prazo_1_dia"


class Notificacao:
    def __init__(
        self,
        user_id: UUID,
        team_id: UUID,
        tipo: TipoNotificacao,
        titulo: str,
        mensagem: str,
        reference_id: UUID | None = None,
        id: UUID | None = None,
        lida: bool = False,
        created_at: datetime | None = None,
    ):
        self.id = id
        self.user_id = user_id
        self.team_id = team_id
        self.tipo = tipo
        self.titulo = titulo
        self.mensagem = mensagem
        self.reference_id = reference_id
        self.lida = lida
        self.created_at = created_at or datetime.now(timezone.utc)

    def marcar_lida(self) -> None:
        self.lida = True
