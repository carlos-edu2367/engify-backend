import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infra.db.models.base import Base, TimestampMixin
from app.domain.entities.team import Team, Plans, Diarist
from app.domain.entities.money import Money


class TeamModel(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False, unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default=Plans.TRIAL.value)
    expiration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relacionamentos — lazy="raise" para detectar N+1 explicitamente
    users: Mapped[list["UserModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="team", lazy="raise"
    )
    diarists: Mapped[list["DiaristModel"]] = relationship(
        back_populates="team", lazy="raise"
    )
    obras: Mapped[list["ObraModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="team", lazy="raise"
    )
    movimentacoes: Mapped[list["MovimentacaoModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="team", lazy="raise"
    )
    pagamentos: Mapped[list["PagamentoAgendadoModel"]] = relationship(  # type: ignore[name-defined]
        back_populates="team", lazy="raise"
    )

    def to_domain(self) -> Team:
        team = object.__new__(Team)
        team.id = self.id
        team.title = self.title
        team.cnpj = self.cnpj
        team.plan = Plans(self.plan)
        team.expiration_date = self.expiration_date
        team.key = self.key
        return team

    @classmethod
    def from_domain(cls, team: Team) -> "TeamModel":
        expiration = team.expiration_date
        if expiration is None:
            expiration = datetime.now(timezone.utc) + timedelta(days=7)
        return cls(
            id=team.id or uuid.uuid4(),
            title=team.title,
            cnpj=team.cnpj,
            plan=team.plan.value,
            expiration_date=expiration,
            key=getattr(team, "key", None),
        )

    def update_from_domain(self, team: Team) -> None:
        self.title = team.title
        self.cnpj = team.cnpj
        self.plan = team.plan.value
        self.expiration_date = team.expiration_date
        self.key = getattr(team, "key", None)


class DiaristModel(Base, TimestampMixin):
    __tablename__ = "diarists"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    valor_diaria_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    valor_diaria_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    chave_pix: Mapped[str] = mapped_column(String(255), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    team: Mapped["TeamModel"] = relationship(back_populates="diarists", lazy="raise")

    __table_args__ = (
        # Busca por time (listagem paginada)
        Index("idx_diarists_team_id", "team_id"),
        # Filtro de soft delete por time
        Index("idx_diarists_team_deleted", "team_id", "is_deleted"),
    )

    def to_domain(self) -> Diarist:
        diarist = object.__new__(Diarist)
        diarist.id = self.id
        diarist.team_id = self.team_id
        diarist.nome = self.nome
        diarist.descricao = self.descricao
        diarist.valor_diaria = Money(self.valor_diaria_amount, self.valor_diaria_currency)
        diarist.chave_pix = self.chave_pix
        diarist.is_deleted = self.is_deleted
        return diarist

    @classmethod
    def from_domain(cls, diarist: Diarist) -> "DiaristModel":
        return cls(
            id=diarist.id or uuid.uuid4(),
            team_id=diarist.team_id,
            nome=diarist.nome,
            descricao=diarist.descricao,
            valor_diaria_amount=diarist.valor_diaria.amount,
            valor_diaria_currency=diarist.valor_diaria.currency,
            chave_pix=diarist.chave_pix,
            is_deleted=diarist.is_deleted,
        )

    def update_from_domain(self, diarist: Diarist) -> None:
        self.nome = diarist.nome
        self.descricao = diarist.descricao
        self.valor_diaria_amount = diarist.valor_diaria.amount
        self.valor_diaria_currency = diarist.valor_diaria.currency
        self.chave_pix = diarist.chave_pix
        self.is_deleted = diarist.is_deleted


