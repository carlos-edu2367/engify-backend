import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.infra.db.models.base import Base, TimestampMixin
from app.domain.entities.notificacao import Notificacao, TipoNotificacao


class NotificacaoModel(Base, TimestampMixin):
    __tablename__ = "notificacoes"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    mensagem: Mapped[str] = mapped_column(String(1000), nullable=False)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    lida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_notificacoes_user_lida", "user_id", "lida"),
        Index("idx_notificacoes_team", "team_id"),
        # Dedup: evita notificação duplicada do mesmo tipo para o mesmo recurso
        Index(
            "uq_notif_user_tipo_ref_prazo",
            "user_id",
            "tipo",
            "reference_id",
            unique=True,
            postgresql_where=tipo.in_([
                TipoNotificacao.PRAZO_7_DIAS.value,
                TipoNotificacao.PRAZO_1_DIA.value,
            ]),
        ),
    )

    def to_domain(self) -> Notificacao:
        n = object.__new__(Notificacao)
        n.id = self.id
        n.user_id = self.user_id
        n.team_id = self.team_id
        n.tipo = TipoNotificacao(self.tipo)
        n.titulo = self.titulo
        n.mensagem = self.mensagem
        n.reference_id = self.reference_id
        n.lida = self.lida
        n.created_at = self.created_at
        return n

    @classmethod
    def from_domain(cls, n: Notificacao) -> "NotificacaoModel":
        return cls(
            id=n.id or uuid.uuid4(),
            user_id=n.user_id,
            team_id=n.team_id,
            tipo=n.tipo.value,
            titulo=n.titulo,
            mensagem=n.mensagem,
            reference_id=n.reference_id,
            lida=n.lida,
        )

    def update_from_domain(self, n: Notificacao) -> None:
        self.lida = n.lida
