from pydantic import BaseModel, field_validator
from uuid import UUID
from decimal import Decimal
from app.domain.entities.team import Plans
from app.domain.entities.user import Roles


# ── Team ─────────────────────────────────────────────────────────────────────

class CreateTeamRequest(BaseModel):
    title: str
    cnpj: str


class CreateFirstUserRequest(BaseModel):
    """Cria o primeiro admin do time. Requer a chave one-time gerada na criação."""
    nome: str
    email: str
    senha: str
    cpf: str
    cnpj: str
    key: str


class UpdateTeamRequest(BaseModel):
    title: str | None = None


class TeamResponse(BaseModel):
    id: UUID
    title: str
    cnpj: str
    plan: Plans
    days_to_expire: int


class TeamCreatedResponse(BaseModel):
    """Retornado na criação do time. Inclui a key one-time (única vez que é exposta)."""
    id: UUID
    title: str
    cnpj: str
    plan: Plans
    key: str


class ExpirationResponse(BaseModel):
    days_to_expire: int


# ── Invite ────────────────────────────────────────────────────────────────────

class InviteUserRequest(BaseModel):
    email: str
    role: Roles

    @field_validator("role")
    @classmethod
    def no_super_admin(cls, v: Roles) -> Roles:
        if v == Roles.SUPER_ADMIN:
            raise ValueError("Não é permitido convidar usuários com role SUPER_ADMIN")
        return v


class InviteResponse(BaseModel):
    id: UUID
    email: str
    role: Roles
    message: str = "Convite enviado com sucesso"


# ── Diarist ───────────────────────────────────────────────────────────────────

class CreateDiaristRequest(BaseModel):
    nome: str
    descricao: str
    valor_diaria: Decimal
    chave_pix: str


class UpdateDiaristRequest(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    valor_diaria: Decimal | None = None
    chave_pix: str | None = None


class DiaristResponse(BaseModel):
    id: UUID
    nome: str
    descricao: str
    valor_diaria: Decimal
    chave_pix: str
