from pydantic import BaseModel, Field
from uuid import UUID
from decimal import Decimal
from typing import Optional, Literal
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


class PayPagamentoResponse(MovimentacaoResponse):
    """Resposta da baixa individual: a movimentacao gerada mais o contexto que
    o front usa para sugerir o anexo do comprovante."""
    pagamento_id: UUID
    requires_receipt: bool = False


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
    requires_receipt: bool = False


class CreatePagamentoParceladoRequest(BaseModel):
    title: str
    details: str
    valor: Decimal  # valor TOTAL, dividido entre as parcelas
    classe: MovClass
    data_agendada: datetime  # vencimento da 1a parcela
    parcelas: int = Field(ge=2, le=36)
    payment_cods: Optional[list[Optional[str]]] = None
    obra_id: Optional[UUID] = None
    diarist_id: Optional[UUID] = None
    requires_receipt: bool = False


class UpdatePagamentoRequest(BaseModel):
    title: Optional[str] = None
    details: Optional[str] = None
    valor: Optional[Decimal] = None
    classe: Optional[MovClass] = None
    data_agendada: Optional[datetime] = None
    payment_cod: Optional[str] = None
    obra_id: Optional[UUID] = None
    requires_receipt: Optional[bool] = None
    apply_to: Literal["self", "future"] = "self"


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
    created_by_user_id: Optional[UUID] = None
    created_by_role: Optional[str] = None
    created_by_name: Optional[str] = None
    created_by_engineer: bool = False
    created_at: Optional[datetime] = None
    parcelamento_id: Optional[UUID] = None
    parcela_numero: Optional[int] = None
    parcela_total: Optional[int] = None
    requires_receipt: bool = False
    receipt_attached: bool = False


class PagamentoReadResponse(PagamentoResponse):
    pix_copy_and_past: Optional[str] = None


# ── Pagamento por Obra (Engenheiro) ───────────────────────────────────────────

class CreateObraPagamentoRequest(BaseModel):
    title: str
    details: str
    valor: Decimal
    data_agendada: datetime
    payment_cod: str
    requires_receipt: bool = False


class CreateObraPagamentoParceladoRequest(BaseModel):
    title: str
    details: str
    valor: Decimal
    data_agendada: datetime
    parcelas: int = Field(ge=2, le=36)
    payment_cods: list[Optional[str]]
    requires_receipt: bool = False


# ── Baixa em Lote ─────────────────────────────────────────────────────────────

class BaixaLoteRequest(BaseModel):
    pagamento_ids: list[UUID]


class BaixaLoteResponse(BaseModel):
    quantidade: int
    valor_total: Decimal
    movimentacao_id: UUID
    comprovante_pendente_count: int = 0


# ── Anexos ─────────────────────────────────────────────────────────────────────

class CreateMovimentacaoAttachmentRequest(BaseModel):
    file_path: str
    file_name: str
    content_type: str
    kind: Literal["documento", "comprovante"] = "documento"


class MovimentacaoAttachmentResponse(BaseModel):
    id: UUID
    movimentacao_id: UUID
    file_path: str
    file_name: str
    content_type: str
    created_at: datetime
    kind: str
    origem_pagamento_id: Optional[UUID] = None


class CreatePagamentoAttachmentRequest(BaseModel):
    file_path: str
    file_name: str
    content_type: str
    replicate_parcelamento: bool = False


class PagamentoAttachmentResponse(BaseModel):
    id: UUID
    pagamento_id: UUID
    file_path: str
    file_name: str
    content_type: str
    created_at: datetime


# ── Comprovacao ────────────────────────────────────────────────────────────────

class ComprovacaoAttachmentResponse(BaseModel):
    id: UUID
    file_path: str
    file_name: str
    content_type: str
    kind: str
    created_at: datetime


class ComprovacaoMovimentacaoResponse(BaseModel):
    id: UUID
    title: str
    valor: Decimal
    data_movimentacao: datetime
    is_lote: bool


class ComprovacaoResponse(BaseModel):
    movimentacao: Optional[ComprovacaoMovimentacaoResponse] = None
    attachments: list[ComprovacaoAttachmentResponse] = []


# ── Fluxo de Caixa ────────────────────────────────────────────────────────────

class FluxoCaixaItemResponse(BaseModel):
    mes: str
    total_entradas: Decimal
    total_saidas: Decimal
    saldo: Decimal


class FluxoCaixaResumoResponse(BaseModel):
    total_entradas: Decimal
    total_saidas: Decimal
    saldo_total: Decimal


class FluxoCaixaResponse(BaseModel):
    periodo: str
    dados: list[FluxoCaixaItemResponse]
    resumo: FluxoCaixaResumoResponse
