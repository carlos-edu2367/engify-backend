from app.domain.entities.user import Roles
from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional

class RegisterUser(BaseModel):
    nome: str
    senha: str
    cpf: str
    solicitacao_id: UUID

class CreateSolicitacaoRegistro(BaseModel):
    """team_id não é enviado pelo cliente — é sempre derivado do JWT do admin autenticado."""
    email: EmailStr
    role: Roles

class Login(BaseModel):
    email: Optional[str] = None
    cpf: Optional[str] = None
    senha: str

class CreateRecoveryCode(BaseModel):
    email: Optional[EmailStr] = None
    cpf: Optional[str] = None

class SimpleUserDisplay(BaseModel):
    user_id: UUID
    nome: str
    email: str
    role: Roles
    