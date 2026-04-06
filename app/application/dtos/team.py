from pydantic import BaseModel, EmailStr
from decimal import Decimal
from typing import Optional
from uuid import UUID


class CreateTeam(BaseModel):
    title: str
    cnpj: str


class CreateFirstUser(BaseModel):
    """DTO para criação do primeiro usuário (admin) de um time.
    Requer a chave de cadastro gerada no momento da criação do time.
    """
    nome: str
    email: EmailStr
    senha: str
    cpf: str
    cnpj: str   # CNPJ do time para localização
    key: str    # Chave one-time gerada na criação do time


class CreateDiarist(BaseModel):
    nome: str
    descricao: str
    valor_diaria: Decimal
    chave_pix: str


class EditDiarist(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    valor_diaria: Optional[Decimal] = None
    chave_pix: Optional[str] = None


class DiaristResponse(BaseModel):
    id: UUID
    nome: str
    descricao: str
    valor_diaria: Decimal
    chave_pix: str
