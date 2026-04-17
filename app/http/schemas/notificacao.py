from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.domain.entities.notificacao import TipoNotificacao


class NotificacaoResponse(BaseModel):
    id: UUID
    tipo: TipoNotificacao
    titulo: str
    mensagem: str
    reference_id: UUID | None = None
    lida: bool
    created_at: datetime


class NotificacaoListResponse(BaseModel):
    items: list[NotificacaoResponse]
    total: int
    page: int
    limit: int


class ContagemNaoLidasResponse(BaseModel):
    nao_lidas: int
