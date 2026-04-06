import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infra.db.models.base import Base, TimestampMixin
from app.domain.entities.user import User, Roles, SolicitacaoCadastro, RecoveryCode
from app.domain.entities.identities import CPF


class UserModel(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False, unique=True, index=True)

    team: Mapped["TeamModel"] = relationship(  # type: ignore[name-defined]
        back_populates="users", lazy="raise"
    )
    recovery_codes: Mapped[list["RecoveryCodeModel"]] = relationship(
        back_populates="user", lazy="raise"
    )

    __table_args__ = (
        Index("idx_users_team_id", "team_id"),
    )

    def to_domain(self) -> User:
        """Requer que self.team esteja carregado (use joinedload)."""
        team_domain = self.team.to_domain()  # levanta se não carregado (lazy="raise")

        user = object.__new__(User)
        user.id = self.id
        user.nome = self.nome
        user.email = self.email
        user.senha_hash = self.senha_hash
        user.role = Roles(self.role)
        user.team = team_domain

        cpf = object.__new__(CPF)
        cpf.value = self.cpf
        user.cpf = cpf

        return user

    @classmethod
    def from_domain(cls, user: User) -> "UserModel":
        return cls(
            id=user.id or uuid.uuid4(),
            team_id=user.team.id,
            nome=user.nome,
            email=user.email,
            senha_hash=user.senha_hash,
            role=user.role.value,
            cpf=user.cpf.value,
        )

    def update_from_domain(self, user: User) -> None:
        self.nome = user.nome
        self.email = user.email
        self.senha_hash = user.senha_hash
        self.role = user.role.value
        self.cpf = user.cpf.value


class SolicitacaoCadastroModel(Base, TimestampMixin):
    __tablename__ = "solicitacoes_cadastro"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    expiration: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        # Busca por e-mail para validar duplicidade de convite
        Index("idx_solicitacoes_email_used", "email", "used"),
        Index("idx_solicitacoes_team", "team_id"),
    )

    def to_domain(self) -> SolicitacaoCadastro:
        s = object.__new__(SolicitacaoCadastro)
        s.id = self.id
        s.team_id = self.team_id
        s.email = self.email
        s.role = Roles(self.role)
        s.expiration = self.expiration
        s.used = self.used
        return s

    @classmethod
    def from_domain(cls, s: SolicitacaoCadastro) -> "SolicitacaoCadastroModel":
        expiration = s.expiration or (datetime.now(timezone.utc) + timedelta(days=7))
        return cls(
            id=s.id or uuid.uuid4(),
            team_id=s.team_id,
            email=s.email,
            role=s.role.value,
            expiration=expiration,
            used=s.used,
        )

    def update_from_domain(self, s: SolicitacaoCadastro) -> None:
        self.used = s.used


class RecoveryCodeModel(Base):
    __tablename__ = "recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped["UserModel"] = relationship(back_populates="recovery_codes", lazy="raise")

    __table_args__ = (
        # Busca por user_id filtrando apenas ativos (used=false) — partial index ideal
        Index("idx_recovery_user_active", "user_id", "used"),
    )

    def to_domain(self) -> RecoveryCode:
        r = object.__new__(RecoveryCode)
        r.id = self.id
        r.user_id = self.user_id
        r.code = self.code
        r.expires = self.expires
        r.used = self.used
        return r

    @classmethod
    def from_domain(cls, r: RecoveryCode) -> "RecoveryCodeModel":
        return cls(
            id=r.id or uuid.uuid4(),
            user_id=r.user_id,
            code=r.code,
            expires=r.expires,
            used=r.used,
        )

    def update_from_domain(self, r: RecoveryCode) -> None:
        self.used = r.used
        self.code = r.code


