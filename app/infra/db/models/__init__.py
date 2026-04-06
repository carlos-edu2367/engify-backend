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
]