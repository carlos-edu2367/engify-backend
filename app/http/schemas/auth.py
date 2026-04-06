from pydantic import BaseModel, EmailStr, model_validator
from uuid import UUID
from app.domain.entities.user import Roles


class LoginRequest(BaseModel):
    email: str | None = None
    cpf: str | None = None
    senha: str

    @model_validator(mode="after")
    def at_least_one_identifier(self) -> "LoginRequest":
        if not self.email and not self.cpf:
            raise ValueError("Informe e-mail ou CPF para login")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    team_id: UUID
    role: Roles
    nome: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    nome: str
    senha: str
    cpf: str
    solicitacao_id: UUID


class RecoveryRequestBody(BaseModel):
    email: EmailStr | None = None
    cpf: str | None = None


class RecoveryVerifyRequest(BaseModel):
    user_id: UUID
    code: str


class RecoveryResetRequest(BaseModel):
    user_id: UUID
    code: str
    new_password: str


class UserResponse(BaseModel):
    id: UUID
    nome: str
    email: str
    role: Roles
    team_id: UUID
