from app.domain.entities.money import Money
from uuid import UUID
from enum import Enum
from datetime import datetime, timezone


class MovimentacaoTypes(Enum):
    ENTRADA = "entrada"
    SAIDA = "saida"


class Natureza(Enum):
    MANUAL = "manual"
    OPEN_FINANCE = "open_finance"


class PaymentStatus(Enum):
    AGUARDANDO = "aguardando"
    PAGO = "pago"


class MovClass(Enum):
    DIARISTA = "diarista"
    SERVICO = "servico"
    CONTRATO = "contrato"
    MATERIAL = "material"
    FIXO = "fixo"
    OPERACIONAL = "operacional"


class Movimentacao():
    def __init__(self, team_id: UUID, title: str,
                 type: MovimentacaoTypes, valor: Money, classe: MovClass,
                 obra_id: UUID = None, id: UUID = None,
                 natureza: Natureza = Natureza.MANUAL,
                 data_movimentacao: datetime = None,
                 pagamento_id: UUID = None,
                 lote_info: dict | None = None,
                 is_deleted: bool = False):
        self.id = id
        self.team_id = team_id
        self.title = title
        self.type = type
        self.valor = valor
        self.obra_id = obra_id
        self.classe = classe
        self.natureza = natureza
        self.data_movimentacao = data_movimentacao or datetime.now(timezone.utc)
        self.pagamento_id = pagamento_id
        # Metadados estruturados do lote — preenchido apenas em baixas em lote
        self.lote_info = lote_info
        self.is_deleted = is_deleted

    def delete(self) -> None:
        self.is_deleted = True


class PagamentoAgendado():
    def __init__(self, team_id: UUID, title: str,
                 details: str, valor: Money, data_agendada: datetime, classe: MovClass,
                 payment_cod: str = None,
                 pix_copy_and_past: str = None,
                 status: PaymentStatus = PaymentStatus.AGUARDANDO,
                 diarist_id: UUID = None, obra_id: UUID = None,
                 id: UUID = None, payment_date: datetime = None):
        self.id = id
        self.team_id = team_id
        self.title = title
        self.details = details
        self.valor = valor
        self.classe = classe
        self.data_agendada = data_agendada
        self.payment_cod = payment_cod
        self.pix_copy_and_past = pix_copy_and_past
        self.status = status
        self.diarist_id = diarist_id
        self.obra_id = obra_id
        self.payment_date = payment_date


class MovimentacaoAttachment():
    """Imagem ou PDF anexado a uma movimentação (comprovante de entrada ou pagamento). Upload feito pelo frontend via signed URL.
    Suporta: image/*, application/pdf
    """
    def __init__(self, movimentacao_id: UUID, team_id: UUID, file_path: str,
                 file_name: str, content_type: str, id: UUID = None):
        self.id = id  # None para novas entidades; o repositório gera o UUID
        self.movimentacao_id = movimentacao_id
        self.team_id = team_id
        self.file_path = file_path
        self.file_name = file_name
        self.content_type = content_type
        self.is_deleted = False
        self.created_at = datetime.now(timezone.utc)

    def delete(self):
        self.is_deleted = True
