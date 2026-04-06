from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from typing import Optional
from datetime import datetime
from app.domain.entities.obra import Status


# ── Obras ─────────────────────────────────────────────────────────────────────

class CreateObraRequest(BaseModel):
    title: str
    responsavel_id: UUID
    description: str
    valor: Optional[Decimal] = None
    data_entrega: Optional[datetime] = None


class UpdateObraRequest(BaseModel):
    title: Optional[str] = None
    responsavel_id: Optional[UUID] = None
    description: Optional[str] = None
    valor: Optional[Decimal] = None
    data_entrega: Optional[datetime] = None


class UpdateStatusRequest(BaseModel):
    status: Status


class ObraResponse(BaseModel):
    id: UUID
    title: str
    description: str
    responsavel_id: UUID
    team_id: UUID
    status: Status
    valor: Optional[Decimal] = None
    data_entrega: Optional[datetime] = None
    created_date: datetime


class ObraListItem(BaseModel):
    id: UUID
    title: str
    status: Status
    responsavel_id: UUID
    valor: Optional[Decimal] = None
    data_entrega: Optional[datetime] = None
    created_date: datetime


# ── Items ─────────────────────────────────────────────────────────────────────

class CreateItemRequest(BaseModel):
    title: str
    descricao: Optional[str] = None
    responsavel_id: Optional[UUID] = None


class UpdateItemRequest(BaseModel):
    title: Optional[str] = None
    descricao: Optional[str] = None
    responsavel_id: Optional[UUID] = None
    status: Optional[Status] = None


class ItemResponse(BaseModel):
    id: UUID
    title: str
    descricao: Optional[str] = None
    responsavel_id: Optional[UUID] = None
    status: Status
    obra_id: UUID


# ── Item Attachments ───────────────────────────────────────────────────────────

class RegisterItemAttachmentRequest(BaseModel):
    file_path: str
    file_name: str
    content_type: str


class ItemAttachmentResponse(BaseModel):
    id: UUID
    item_id: UUID
    file_path: str
    file_name: str
    content_type: str
    created_at: datetime


# ── Mural ──────────────────────────────────────────────────────────────────────

class CreateMuralPostRequest(BaseModel):
    content: str
    mentions: Optional[list[UUID]] = []


class RegisterMuralAttachmentRequest(BaseModel):
    file_path: str
    file_name: str
    content_type: str


class MuralAttachmentResponse(BaseModel):
    id: UUID
    post_id: UUID
    file_path: str
    file_name: str
    content_type: str
    created_at: datetime


class MuralPostResponse(BaseModel):
    id: UUID
    obra_id: UUID
    author_id: Optional[UUID] = None
    author_nome: Optional[str] = None
    content: str
    mentions: list[UUID]
    attachments: list[MuralAttachmentResponse]
    created_at: datetime


# ── Cliente (visão somente-leitura) ───────────────────────────────────────────

class ItemClienteView(BaseModel):
    id: UUID
    title: str
    status: Status


class ImageClienteView(BaseModel):
    id: UUID
    file_name: str
    file_path: str


class ObraClienteResponse(BaseModel):
    id: UUID
    title: str
    description: str
    status: Status
    data_entrega: Optional[datetime] = None
    items: list[ItemClienteView]
    images: list[ImageClienteView]
