from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from typing import Optional
from datetime import datetime
from app.domain.entities.obra import Status

class CreateObraDTO(BaseModel):
    title: str
    team_id: UUID
    responsavel_id: UUID
    description: str
    valor: Optional[Decimal] = None
    data_entrega: Optional[datetime] = None

class CreateDiary(BaseModel):
    diarista_id: UUID
    obra_id: UUID
    descricao_diaria: Optional[str] = None
    quantidade_diaria: float
    data: Optional[datetime] = None
    data_pagamento: Optional[datetime] = None  # quando o pagamento deve ser efetuado

class DiariesResponse(BaseModel):
    id: UUID
    diarist_id: UUID
    diarist_name: str
    descricao_diaria: Optional[str]
    obra_id: UUID
    obra_title: str
    quantidade: float
    data: datetime

class EditDiary(BaseModel):
    descricao_diaria: Optional[str] = None
    quantidade_diaria: Optional[float] = None
    data: Optional[datetime] = None

class EditObraInfo(BaseModel):
    title: Optional[str] = None
    responsavel_id: Optional[UUID] = None
    description: Optional[str] = None
    valor: Optional[Decimal] = None
    data_entrega: Optional[datetime] = None

class CreateItem(BaseModel):
    title: str
    obra_id: UUID
    team_id: UUID  # injetado pelo router a partir do JWT (request.state.team_id)
    descricao: Optional[str] = None
    responsavel_id: Optional[UUID] = None

class UpdateItem(BaseModel):
    title: Optional[str] = None
    descricao: Optional[str] = None
    responsavel_id: Optional[UUID] = None
    status: Optional[Status] = None


# ── Mural ──────────────────────────────────────────────────────────────────────

class CreateMuralPost(BaseModel):
    obra_id: UUID
    team_id: UUID
    author_id: UUID
    content: str
    mentions: list[UUID] = []


class CreateMuralAttachment(BaseModel):
    post_id: UUID
    team_id: UUID
    file_path: str
    file_name: str
    content_type: str


# ── ItemAttachment ─────────────────────────────────────────────────────────────

class CreateItemAttachment(BaseModel):
    item_id: UUID
    team_id: UUID
    file_path: str
    file_name: str
    content_type: str


# ── ObraImage ──────────────────────────────────────────────────────────────────

class CreateObraImage(BaseModel):
    obra_id: UUID
    team_id: UUID
    file_path: str
    file_name: str
    content_type: str

