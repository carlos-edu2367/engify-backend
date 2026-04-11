from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from typing import Optional
from datetime import datetime
from app.domain.entities.financeiro import MovimentacaoTypes, MovClass, Natureza, PaymentStatus


# ── Movimentações ─────────────────────────────────────────────────────────────

class CreateMovimentacaoRequest(BaseModel):
    title: str
    type: MovimentacaoTypes
    valor: Decimal
    classe: MovClass
    obra_id: Optional[UUID] = None


class MovimentacaoResponse(BaseModel):
    id: UUID
    title: str
    type: MovimentacaoTypes
    valor: Decimal
    classe: MovClass
    natureza: Natureza
    obra_id: Optional[UUID] = None
    pagamento_id: Optional[UUID] = None
    data_movimentacao: datetime


# ── Pagamentos Agendados ───────────────────────────────────────────────────────

class CreatePagamentoRequest(BaseModel):
    title: str
    details: str
    valor: Decimal
    classe: MovClass
    data_agendada: datetime
    payment_cod: Optional[str] = None
    obra_id: Optional[UUID] = None
    diarist_id: Optional[UUID] = None


class UpdatePagamentoRequest(BaseModel):
    title: Optional[str] = None
    details: Optional[str] = None
    valor: Optional[Decimal] = None
    data_agendada: Optional[datetime] = None
    payment_cod: Optional[str] = None
    obra_id: Optional[UUID] = None


class PagamentoResponse(BaseModel):
    id: UUID
    title: str
    details: str
    valor: Decimal
    classe: MovClass
    status: PaymentStatus
    data_agendada: datetime
    payment_cod: Optional[str] = None
    obra_id: Optional[UUID] = None
    diarist_id: Optional[UUID] = None
    payment_date: Optional[datetime] = None


class PagamentoReadResponse(PagamentoResponse):
    pix_copy_and_past: Optional[str] = None


# ── Pagamento por Obra (Engenheiro) ───────────────────────────────────────────

class CreateObraPagamentoRequest(BaseModel):
    title: str
    details: str
    valor: Decimal
    data_agendada: datetime
    payment_cod: str


# ── Anexos ─────────────────────────────────────────────────────────────────────

class CreateMovimentacaoAttachmentRequest(BaseModel):
    file_path: str
    file_name: str
    content_type: str


class MovimentacaoAttachmentResponse(BaseModel):
    id: UUID
    movimentacao_id: UUID
    file_path: str
    file_name: str
    content_type: str
    created_at: datetime
