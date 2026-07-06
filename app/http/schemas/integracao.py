from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ── OAuth ────────────────────────────────────────────────────────────────────

class AuthorizeConsentRequest(BaseModel):
    """Consentimento do admin Engify autorizando o vínculo com uma organização Arcaika."""
    client_id: str
    redirect_uri: str
    scope: str  # separado por espaço
    code_challenge: str = Field(min_length=20, max_length=200)
    code_challenge_method: str = "S256"
    state: str | None = None
    arcaika_organizacao_id: UUID
    default_responsavel_id: UUID
    default_categoria_id: UUID | None = None


class AuthorizeConsentResponse(BaseModel):
    redirect_to: str  # redirect_uri + ?code=...&state=...


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int
    scope: str
    engify_team_id: UUID


# ── API de integração (chamada pelo Arcaika) ─────────────────────────────────

class ExternalRef(BaseModel):
    orcamento_id: UUID
    solicitacao_id: UUID
    organizacao_id: UUID


class DetalhamentoResumoItem(BaseModel):
    ambiente: str
    total: Decimal


class CreateObraFromOrcamentoRequest(BaseModel):
    external_ref: ExternalRef
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    valor: Decimal | None = None
    data_entrega: datetime | None = None
    responsavel_id: UUID | None = None
    categoria_id: UUID | None = None
    detalhamento_resumo: list[DetalhamentoResumoItem] = Field(default_factory=list)


class CreateObraResponse(BaseModel):
    obra_id: UUID
    status: str
    public_url: str
    created_at: datetime
    already_existed: bool = False


class ObraStatusResponse(BaseModel):
    obra_id: UUID
    status: str
    public_url: str
    total_recebido: Decimal
    data_entrega: datetime | None
    updated_at: datetime | None = None


class UnlinkedObraItem(BaseModel):
    obra_id: UUID
    title: str
    status: str
    valor: Decimal | None = None
    data_entrega: datetime | None = None
    created_at: datetime
    public_url: str


class UnlinkedObrasResponse(BaseModel):
    items: list[UnlinkedObraItem]
    page: int
    has_more: bool


class LinkObraRequest(BaseModel):
    external_ref: ExternalRef


class LinkObraResponse(CreateObraResponse):
    already_linked: bool = False


class RegisterWebhookRequest(BaseModel):
    url: str = Field(pattern=r"^https://.+")


class RegisterWebhookResponse(BaseModel):
    webhook_url: str
    webhook_secret: str
