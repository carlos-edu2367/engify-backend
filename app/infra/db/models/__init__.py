# Importar todos os models aqui garante que o SQLAlchemy registre todas as
# classes no mapper antes de resolver as string forward references nos relacionamentos.
# A ordem importa: dependências primeiro.
from app.infra.db.models.base import Base, TimestampMixin
from app.infra.db.models.team_model import TeamModel, DiaristModel
from app.infra.db.models.user_model import UserModel, SolicitacaoCadastroModel, RecoveryCodeModel
from app.infra.db.models.obra_model import (
    ObraModel, ItemModel, ItemAttachmentModel, ImageModel, DiaryModel,
    MuralPostModel, MuralAttachmentModel,
)
from app.infra.db.models.financeiro_model import (
    MovimentacaoModel, PagamentoAgendadoModel, MovimentacaoAttachmentModel
)
from app.infra.db.models.notificacao_model import NotificacaoModel
from app.infra.db.models.report_job_model import ReportJobModel
from app.infra.db.models.rh_model import (
    AjustePontoModel,
    AtestadoModel,
    FeriasModel,
    FuncionarioModel,
    HoleriteModel,
    HorarioIntervaloModel,
    HorarioTrabalhoModel,
    HorarioTurnoModel,
    LocalPontoModel,
    RegistroPontoModel,
    RhAuditLogModel,
    RhIdempotencyKeyModel,
    RhSalarioHistoricoModel,
    TipoAtestadoModel,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "TeamModel",
    "DiaristModel",
    "UserModel",
    "SolicitacaoCadastroModel",
    "RecoveryCodeModel",
    "ObraModel",
    "ItemModel",
    "ItemAttachmentModel",
    "ImageModel",
    "DiaryModel",
    "MuralPostModel",
    "MuralAttachmentModel",
    "MovimentacaoModel",
    "PagamentoAgendadoModel",
    "MovimentacaoAttachmentModel",
    "NotificacaoModel",
    "ReportJobModel",
    "FuncionarioModel",
    "HorarioTrabalhoModel",
    "HorarioTurnoModel",
    "HorarioIntervaloModel",
    "FeriasModel",
    "LocalPontoModel",
    "RegistroPontoModel",
    "AjustePontoModel",
    "TipoAtestadoModel",
    "AtestadoModel",
    "HoleriteModel",
    "RhAuditLogModel",
    "RhIdempotencyKeyModel",
    "RhSalarioHistoricoModel",
]
