from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from typing import Optional, Literal
from datetime import datetime
from app.domain.entities.financeiro import MovimentacaoTypes, MovClass, Natureza, PaymentStatus


class CreateMovimentacaoDTO(BaseModel):
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


class CreatePagamentoDTO(BaseModel):
    title: str
    details: str
    valor: Decimal
    classe: MovClass
    data_agendada: datetime
    payment_cod: Optional[str] = None
    obra_id: Optional[UUID] = None
    diarist_id: Optional[UUID] = None
    requires_receipt: bool = False


class CreatePagamentoParceladoDTO(BaseModel):
    title: str
    details: str
    valor: Decimal  # valor TOTAL do parcelamento
    classe: MovClass
    data_agendada: datetime  # vencimento da 1a parcela
    parcelas: int
    payment_cods: Optional[list[Optional[str]]] = None
    obra_id: Optional[UUID] = None
    diarist_id: Optional[UUID] = None
    requires_receipt: bool = False


class EditPagamentoDTO(BaseModel):
    title: Optional[str] = None
    details: Optional[str] = None
    valor: Optional[Decimal] = None
    classe: Optional[MovClass] = None
    data_agendada: Optional[datetime] = None
    payment_cod: Optional[str] = None
    obra_id: Optional[UUID] = None
    requires_receipt: Optional[bool] = None
    # "self" edita so o pagamento alvo; "future" propaga os campos comuns para
    # as parcelas seguintes do mesmo parcelamento que ainda estao aguardando.
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


class AddMovimentacaoAttachmentDTO(BaseModel):
    file_path: str
    file_name: str
    content_type: str
    kind: Literal["documento", "comprovante"] = "documento"


class AddPagamentoAttachmentDTO(BaseModel):
    file_path: str
    file_name: str
    content_type: str
    # Quando True e o pagamento faz parte de um parcelamento, registra o mesmo
    # arquivo em todas as parcelas aguardando do grupo (carne, contrato etc.).
    replicate_parcelamento: bool = False


class PagamentoFiltersDTO(BaseModel):
    status: Optional[PaymentStatus] = None
    obra_id: Optional[UUID] = None
    created_by_user_id: Optional[UUID] = None
    # Recorte por data de vencimento (data_agendada).
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    # True lista somente pagamentos ja pagos que pediam comprovante e ainda
    # nao tiveram um anexado. False/None nao filtra nada.
    comprovante_pendente: Optional[bool] = None


class MovimentacaoFiltersDTO(BaseModel):
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    obra_id: Optional[UUID] = None
    classe: Optional[MovClass] = None


class BaixaLoteDTO(BaseModel):
    pagamento_ids: list[UUID]
    team_id: UUID


class LotePagamentoResultDTO(BaseModel):
    quantidade: int
    valor_total: Decimal
    movimentacao_id: UUID
    comprovante_pendente_count: int = 0


class ComprovacaoAttachmentDTO(BaseModel):
    id: UUID
    file_path: str
    file_name: str
    content_type: str
    kind: str
    created_at: datetime


class ComprovacaoMovimentacaoDTO(BaseModel):
    id: UUID
    title: str
    valor: Decimal
    data_movimentacao: datetime
    is_lote: bool


class ComprovacaoDTO(BaseModel):
    movimentacao: Optional[ComprovacaoMovimentacaoDTO] = None
    attachments: list[ComprovacaoAttachmentDTO] = []


class FluxoCaixaItemDTO(BaseModel):
    mes: str
    total_entradas: Decimal
    total_saidas: Decimal
    saldo: Decimal


class FluxoCaixaResumoDTO(BaseModel):
    total_entradas: Decimal
    total_saidas: Decimal
    saldo_total: Decimal


class FluxoCaixaDTO(BaseModel):
    periodo: str
    dados: list[FluxoCaixaItemDTO]
    resumo: FluxoCaixaResumoDTO
