import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, Boolean, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infra.db.models.base import Base, TimestampMixin
from app.domain.entities.financeiro import (
    Movimentacao, MovimentacaoTypes, Natureza, MovClass,
    PagamentoAgendado, PaymentStatus, MovimentacaoAttachment,
)
from app.domain.entities.money import Money


class MovimentacaoModel(Base, TimestampMixin):
    __tablename__ = "movimentacoes"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    # obra_id é nullable: pagamentos não precisam estar vinculados a uma obra
    obra_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("obras.id", ondelete="SET NULL"),
        nullable=True,
    )
    # pagamento_id é nullable: movimentações manuais não têm pagamento agendado
    pagamento_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pagamentos_agendados.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    valor_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    valor_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    classe: Mapped[str] = mapped_column(String(20), nullable=False)
    natureza: Mapped[str] = mapped_column(String(20), nullable=False, default=Natureza.MANUAL.value)
    data_movimentacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    team: Mapped["TeamModel"] = relationship(  # type: ignore[name-defined]
        back_populates="movimentacoes", lazy="raise"
    )
    attachments: Mapped[list["MovimentacaoAttachmentModel"]] = relationship(
        back_populates="movimentacao", lazy="raise"
    )

    __table_args__ = (
        # Listagem por time + período (principal consulta financeira)
        Index("idx_movimentacoes_team_data", "team_id", "data_movimentacao"),
        # Filtro por tipo dentro do time
        Index("idx_movimentacoes_team_type", "team_id", "type"),
        # Movimentações de uma obra específica (nullable, só indexa quando preenchido)
        Index("idx_movimentacoes_obra", "obra_id"),
    )

    def update_from_domain(self, m: Movimentacao) -> None:
        self.title = m.title
        self.type = m.type.value
        self.valor_amount = m.valor.amount
        self.valor_currency = m.valor.currency
        self.classe = m.classe.value
        self.natureza = m.natureza.value
        self.data_movimentacao = m.data_movimentacao
        self.obra_id = m.obra_id
        self.pagamento_id = m.pagamento_id

    def to_domain(self) -> Movimentacao:
        m = object.__new__(Movimentacao)
        m.id = self.id
        m.team_id = self.team_id
        m.obra_id = self.obra_id
        m.pagamento_id = self.pagamento_id
        m.title = self.title
        m.type = MovimentacaoTypes(self.type)
        m.valor = Money(self.valor_amount, self.valor_currency)
        m.classe = MovClass(self.classe)
        m.natureza = Natureza(self.natureza)
        m.data_movimentacao = self.data_movimentacao
        return m

    @classmethod
    def from_domain(cls, m: Movimentacao) -> "MovimentacaoModel":
        return cls(
            id=m.id or uuid.uuid4(),
            team_id=m.team_id,
            obra_id=m.obra_id,
            pagamento_id=m.pagamento_id,
            title=m.title,
            type=m.type.value,
            valor_amount=m.valor.amount,
            valor_currency=m.valor.currency,
            classe=m.classe.value,
            natureza=m.natureza.value,
            data_movimentacao=m.data_movimentacao or datetime.now(timezone.utc),
        )


class PagamentoAgendadoModel(Base, TimestampMixin):
    __tablename__ = "pagamentos_agendados"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Pagamento pode ou não estar vinculado a uma obra
    obra_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("obras.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Pagamento pode ou não estar vinculado a um diarista
    diarist_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("diarists.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    valor_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    valor_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    classe: Mapped[str] = mapped_column(String(20), nullable=False)
    data_agendada: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_cod: Mapped[str | None] = mapped_column(Text, nullable=True)
    pix_copy_and_past: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PaymentStatus.AGUARDANDO.value
    )
    payment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    team: Mapped["TeamModel"] = relationship(  # type: ignore[name-defined]
        back_populates="pagamentos", lazy="raise"
    )

    __table_args__ = (
        # Listagem por time + data agendada
        Index("idx_pagamentos_team_data", "team_id", "data_agendada"),
        # Filtro por status dentro do time (aguardando pagamentos)
        Index("idx_pagamentos_team_status", "team_id", "status"),
        # Pagamentos de uma obra específica
        Index("idx_pagamentos_obra", "obra_id"),
    )

    def to_domain(self) -> PagamentoAgendado:
        p = object.__new__(PagamentoAgendado)
        p.id = self.id
        p.team_id = self.team_id
        p.obra_id = self.obra_id
        p.diarist_id = self.diarist_id
        p.title = self.title
        p.details = self.details
        p.valor = Money(self.valor_amount, self.valor_currency)
        p.classe = MovClass(self.classe)
        p.data_agendada = self.data_agendada
        p.payment_cod = self.payment_cod
        p.pix_copy_and_past = self.pix_copy_and_past
        p.status = PaymentStatus(self.status)
        p.payment_date = self.payment_date
        return p

    @classmethod
    def from_domain(cls, p: PagamentoAgendado) -> "PagamentoAgendadoModel":
        return cls(
            id=p.id or uuid.uuid4(),
            team_id=p.team_id,
            obra_id=p.obra_id,
            diarist_id=p.diarist_id,
            title=p.title,
            details=p.details,
            valor_amount=p.valor.amount,
            valor_currency=p.valor.currency,
            classe=p.classe.value,
            data_agendada=p.data_agendada,
            payment_cod=p.payment_cod,
            pix_copy_and_past=p.pix_copy_and_past,
            status=p.status.value,
            payment_date=p.payment_date,
        )

    def update_from_domain(self, p: PagamentoAgendado) -> None:
        self.status = p.status.value
        self.payment_date = p.payment_date
        self.payment_cod = p.payment_cod
        self.pix_copy_and_past = p.pix_copy_and_past
        self.title = p.title
        self.details = p.details
        self.valor_amount = p.valor.amount
        self.valor_currency = p.valor.currency
        self.data_agendada = p.data_agendada
        self.obra_id = p.obra_id
        self.diarist_id = p.diarist_id


class MovimentacaoAttachmentModel(Base, TimestampMixin):
    __tablename__ = "movimentacao_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    movimentacao_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("movimentacoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalizado para RLS por tenant
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Suporta image/* e application/pdf
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    movimentacao: Mapped["MovimentacaoModel"] = relationship(
        back_populates="attachments", lazy="raise"
    )

    __table_args__ = (
        Index("idx_mov_attachments_movimentacao", "movimentacao_id", "is_deleted"),
        Index("idx_mov_attachments_team", "team_id"),
    )

    def to_domain(self) -> MovimentacaoAttachment:
        a = object.__new__(MovimentacaoAttachment)
        a.id = self.id
        a.movimentacao_id = self.movimentacao_id
        a.team_id = self.team_id
        a.file_path = self.file_path
        a.file_name = self.file_name
        a.content_type = self.content_type
        a.is_deleted = self.is_deleted
        a.created_at = self.created_at
        return a

    @classmethod
    def from_domain(cls, a: MovimentacaoAttachment) -> "MovimentacaoAttachmentModel":
        return cls(
            id=a.id or uuid.uuid4(),
            movimentacao_id=a.movimentacao_id,
            team_id=a.team_id,
            file_path=a.file_path,
            file_name=a.file_name,
            content_type=a.content_type,
            is_deleted=a.is_deleted,
        )

    def update_from_domain(self, a: MovimentacaoAttachment) -> None:
        self.is_deleted = a.is_deleted

