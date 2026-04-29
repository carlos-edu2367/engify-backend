import uuid
from datetime import datetime, time, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.entities.money import Money
from app.domain.entities.rh import (
    AjustePonto,
    Atestado,
    Ferias,
    Funcionario,
    Holerite,
    HorarioTrabalho,
    IntervaloHorario,
    LocalPonto,
    RegistroPonto,
    RhAuditLog,
    RhIdempotencyKey,
    RhSalarioHistorico,
    StatusAjuste,
    StatusAtestado,
    StatusFerias,
    StatusHolerite,
    StatusPonto,
    TipoAtestado,
    TipoPonto,
    TurnoHorario,
)
from app.domain.entities.identities import CPF
from app.infra.db.models.base import Base, TimestampMixin


class FuncionarioModel(Base, TimestampMixin):
    __tablename__ = "rh_funcionarios"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False)
    cargo: Mapped[str] = mapped_column(String(120), nullable=False)
    salario_base_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    salario_base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    data_admissao: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    horario_trabalho: Mapped["HorarioTrabalhoModel | None"] = relationship(back_populates="funcionario", lazy="raise")
    turnos_ponto: Mapped[list["RegistroPontoModel"]] = relationship(back_populates="funcionario", lazy="raise")

    __table_args__ = (
        Index(
            "uq_rh_funcionarios_team_cpf_active",
            "team_id",
            "cpf",
            unique=True,
            postgresql_where=(is_deleted == False),  # noqa: E712
        ),
        Index(
            "uq_rh_funcionarios_team_user_active",
            "team_id",
            "user_id",
            unique=True,
            postgresql_where=(is_deleted == False),  # noqa: E712
        ),
        Index("idx_rh_funcionarios_team_active_deleted", "team_id", "is_active", "is_deleted"),
    )

    def to_domain(self) -> Funcionario:
        funcionario = object.__new__(Funcionario)
        funcionario.id = self.id
        funcionario.team_id = self.team_id
        funcionario.nome = self.nome
        cpf = object.__new__(CPF)
        cpf.value = self.cpf
        funcionario.cpf = cpf
        funcionario.cargo = self.cargo
        funcionario.salario_base = Money(self.salario_base_amount, self.salario_base_currency)
        funcionario.data_admissao = self.data_admissao
        funcionario.user_id = self.user_id
        funcionario.is_active = self.is_active
        funcionario.is_deleted = self.is_deleted
        funcionario.horario_trabalho = None
        return funcionario

    @classmethod
    def from_domain(cls, funcionario: Funcionario) -> "FuncionarioModel":
        return cls(
            id=funcionario.id or uuid.uuid4(),
            team_id=funcionario.team_id,
            user_id=funcionario.user_id,
            nome=funcionario.nome,
            cpf=funcionario.cpf.value,
            cargo=funcionario.cargo,
            salario_base_amount=funcionario.salario_base.amount,
            salario_base_currency=funcionario.salario_base.currency,
            data_admissao=funcionario.data_admissao,
            is_active=funcionario.is_active,
            is_deleted=funcionario.is_deleted,
        )

    def update_from_domain(self, funcionario: Funcionario) -> None:
        self.user_id = funcionario.user_id
        self.nome = funcionario.nome
        self.cpf = funcionario.cpf.value
        self.cargo = funcionario.cargo
        self.salario_base_amount = funcionario.salario_base.amount
        self.salario_base_currency = funcionario.salario_base.currency
        self.data_admissao = funcionario.data_admissao
        self.is_active = funcionario.is_active
        self.is_deleted = funcionario.is_deleted


class HorarioTrabalhoModel(Base, TimestampMixin):
    __tablename__ = "rh_horarios_trabalho"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    funcionario_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    funcionario: Mapped["FuncionarioModel"] = relationship(back_populates="horario_trabalho", lazy="raise")
    turnos: Mapped[list["HorarioTurnoModel"]] = relationship(back_populates="horario", lazy="raise", cascade="all, delete-orphan")

    __table_args__ = (
        Index(
            "uq_rh_horarios_team_funcionario_active",
            "team_id",
            "funcionario_id",
            unique=True,
            postgresql_where=(is_deleted == False),  # noqa: E712
        ),
    )

    def to_domain(self) -> HorarioTrabalho:
        horario = object.__new__(HorarioTrabalho)
        horario.id = self.id
        horario.team_id = self.team_id
        horario.funcionario_id = self.funcionario_id
        horario.turnos = [turno.to_domain() for turno in self.turnos]
        horario.is_deleted = self.is_deleted
        return horario

    @classmethod
    def from_domain(cls, horario: HorarioTrabalho) -> "HorarioTrabalhoModel":
        return cls(
            id=horario.id or uuid.uuid4(),
            team_id=horario.team_id,
            funcionario_id=horario.funcionario_id,
            is_deleted=horario.is_deleted,
        )

    def update_from_domain(self, horario: HorarioTrabalho) -> None:
        self.funcionario_id = horario.funcionario_id
        self.is_deleted = horario.is_deleted


class HorarioTurnoModel(Base):
    __tablename__ = "rh_horario_turnos"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    horario_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_horarios_trabalho.id", ondelete="CASCADE"), nullable=False)
    dia_semana: Mapped[int] = mapped_column(Integer, nullable=False)
    hora_entrada: Mapped[time] = mapped_column(nullable=False)
    hora_saida: Mapped[time] = mapped_column(nullable=False)

    horario: Mapped["HorarioTrabalhoModel"] = relationship(back_populates="turnos", lazy="raise")
    intervalos: Mapped[list["HorarioIntervaloModel"]] = relationship(back_populates="turno", lazy="raise", cascade="all, delete-orphan")

    __table_args__ = (
        Index("uq_rh_horario_turnos_horario_dia", "horario_id", "dia_semana", unique=True),
    )

    def to_domain(self) -> TurnoHorario:
        return TurnoHorario(
            dia_semana=self.dia_semana,
            hora_entrada=self.hora_entrada,
            hora_saida=self.hora_saida,
            intervalos=[intervalo.to_domain() for intervalo in sorted(self.intervalos, key=lambda item: item.ordem)],
        )

    @classmethod
    def from_domain(cls, horario_id: uuid.UUID, turno: TurnoHorario) -> "HorarioTurnoModel":
        return cls(
            id=uuid.uuid4(),
            horario_id=horario_id,
            dia_semana=turno.dia_semana,
            hora_entrada=turno.hora_entrada,
            hora_saida=turno.hora_saida,
        )


class HorarioIntervaloModel(Base):
    __tablename__ = "rh_horario_intervalos"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turno_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_horario_turnos.id", ondelete="CASCADE"), nullable=False)
    hora_inicio: Mapped[time] = mapped_column(nullable=False)
    hora_fim: Mapped[time] = mapped_column(nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    turno: Mapped["HorarioTurnoModel"] = relationship(back_populates="intervalos", lazy="raise")

    __table_args__ = (
        Index("idx_rh_horario_intervalos_turno_ordem", "turno_id", "ordem"),
    )

    def to_domain(self) -> IntervaloHorario:
        return IntervaloHorario(hora_inicio=self.hora_inicio, hora_fim=self.hora_fim)

    @classmethod
    def from_domain(cls, turno_id: uuid.UUID, intervalo: IntervaloHorario, ordem: int) -> "HorarioIntervaloModel":
        return cls(
            id=uuid.uuid4(),
            turno_id=turno_id,
            hora_inicio=intervalo.hora_inicio,
            hora_fim=intervalo.hora_fim,
            ordem=ordem,
        )


class FeriasModel(Base, TimestampMixin):
    __tablename__ = "rh_ferias"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    funcionario_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False)
    data_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_fim: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StatusFerias.SOLICITADO.value)
    motivo_rejeicao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_rh_ferias_team_funcionario_status_periodo", "team_id", "funcionario_id", "status", "data_inicio", "data_fim"),
    )

    def to_domain(self) -> Ferias:
        ferias = object.__new__(Ferias)
        ferias.id = self.id
        ferias.team_id = self.team_id
        ferias.funcionario_id = self.funcionario_id
        ferias.data_inicio = self.data_inicio
        ferias.data_fim = self.data_fim
        ferias.status = StatusFerias(self.status)
        ferias.motivo_rejeicao = self.motivo_rejeicao
        ferias.is_deleted = self.is_deleted
        return ferias

    @classmethod
    def from_domain(cls, ferias: Ferias) -> "FeriasModel":
        return cls(
            id=ferias.id or uuid.uuid4(),
            team_id=ferias.team_id,
            funcionario_id=ferias.funcionario_id,
            data_inicio=ferias.data_inicio,
            data_fim=ferias.data_fim,
            status=ferias.status.value,
            motivo_rejeicao=ferias.motivo_rejeicao,
            is_deleted=ferias.is_deleted,
        )

    def update_from_domain(self, ferias: Ferias) -> None:
        self.data_inicio = ferias.data_inicio
        self.data_fim = ferias.data_fim
        self.status = ferias.status.value
        self.motivo_rejeicao = ferias.motivo_rejeicao
        self.is_deleted = ferias.is_deleted


class LocalPontoModel(Base, TimestampMixin):
    __tablename__ = "rh_locais_ponto"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    funcionario_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    raio_metros: Mapped[float] = mapped_column(nullable=False, default=100.0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_rh_locais_ponto_team_funcionario_deleted", "team_id", "funcionario_id", "is_deleted"),
    )

    def to_domain(self) -> LocalPonto:
        local_ponto = object.__new__(LocalPonto)
        local_ponto.id = self.id
        local_ponto.team_id = self.team_id
        local_ponto.funcionario_id = self.funcionario_id
        local_ponto.nome = self.nome
        local_ponto.latitude = self.latitude
        local_ponto.longitude = self.longitude
        local_ponto.raio_metros = self.raio_metros
        local_ponto.is_deleted = self.is_deleted
        return local_ponto

    @classmethod
    def from_domain(cls, local_ponto: LocalPonto) -> "LocalPontoModel":
        return cls(
            id=local_ponto.id or uuid.uuid4(),
            team_id=local_ponto.team_id,
            funcionario_id=local_ponto.funcionario_id,
            nome=local_ponto.nome,
            latitude=local_ponto.latitude,
            longitude=local_ponto.longitude,
            raio_metros=local_ponto.raio_metros,
            is_deleted=local_ponto.is_deleted,
        )

    def update_from_domain(self, local_ponto: LocalPonto) -> None:
        self.nome = local_ponto.nome
        self.latitude = local_ponto.latitude
        self.longitude = local_ponto.longitude
        self.raio_metros = local_ponto.raio_metros
        self.is_deleted = local_ponto.is_deleted


class RegistroPontoModel(Base, TimestampMixin):
    __tablename__ = "rh_registros_ponto"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    funcionario_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StatusPonto.VALIDADO.value)
    local_ponto_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_locais_ponto.id", ondelete="SET NULL"), nullable=True)
    client_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gps_accuracy_meters: Mapped[float | None] = mapped_column(nullable=True)
    device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    denial_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    funcionario: Mapped["FuncionarioModel"] = relationship(back_populates="turnos_ponto", lazy="raise")

    __table_args__ = (
        Index("idx_rh_registros_ponto_team_funcionario_timestamp", "team_id", "funcionario_id", "timestamp"),
        Index("idx_rh_registros_ponto_team_funcionario_status_timestamp", "team_id", "funcionario_id", "status", "timestamp"),
        Index("idx_rh_registros_ponto_team_timestamp", "team_id", "timestamp"),
    )

    def to_domain(self) -> RegistroPonto:
        registro = object.__new__(RegistroPonto)
        registro.id = self.id
        registro.team_id = self.team_id
        registro.funcionario_id = self.funcionario_id
        registro.tipo = TipoPonto(self.tipo)
        registro.timestamp = self.timestamp
        registro.latitude = self.latitude
        registro.longitude = self.longitude
        registro.status = StatusPonto(self.status)
        registro.local_ponto_id = self.local_ponto_id
        registro.client_timestamp = self.client_timestamp
        registro.gps_accuracy_meters = self.gps_accuracy_meters
        registro.device_fingerprint = self.device_fingerprint
        registro.ip_hash = self.ip_hash
        registro.denial_reason = self.denial_reason
        registro.is_deleted = self.is_deleted
        return registro

    @classmethod
    def from_domain(cls, registro: RegistroPonto) -> "RegistroPontoModel":
        return cls(
            id=registro.id or uuid.uuid4(),
            team_id=registro.team_id,
            funcionario_id=registro.funcionario_id,
            tipo=registro.tipo.value,
            timestamp=registro.timestamp,
            latitude=registro.latitude,
            longitude=registro.longitude,
            status=registro.status.value,
            local_ponto_id=registro.local_ponto_id,
            client_timestamp=registro.client_timestamp,
            gps_accuracy_meters=registro.gps_accuracy_meters,
            device_fingerprint=registro.device_fingerprint,
            ip_hash=registro.ip_hash,
            denial_reason=registro.denial_reason,
            is_deleted=registro.is_deleted,
        )

    def update_from_domain(self, registro: RegistroPonto) -> None:
        self.tipo = registro.tipo.value
        self.timestamp = registro.timestamp
        self.latitude = registro.latitude
        self.longitude = registro.longitude
        self.status = registro.status.value
        self.local_ponto_id = registro.local_ponto_id
        self.client_timestamp = registro.client_timestamp
        self.gps_accuracy_meters = registro.gps_accuracy_meters
        self.device_fingerprint = registro.device_fingerprint
        self.ip_hash = registro.ip_hash
        self.denial_reason = registro.denial_reason
        self.is_deleted = registro.is_deleted


class AjustePontoModel(Base, TimestampMixin):
    __tablename__ = "rh_ajustes_ponto"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    funcionario_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False)
    data_referencia: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    justificativa: Mapped[str] = mapped_column(String(1000), nullable=False)
    hora_entrada_solicitada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hora_saida_solicitada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StatusAjuste.PENDENTE.value)
    motivo_rejeicao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_rh_ajustes_ponto_team_funcionario_status_data", "team_id", "funcionario_id", "status", "data_referencia"),
        Index("idx_rh_ajustes_ponto_team_status_created", "team_id", "status", "created_at"),
    )

    def to_domain(self) -> AjustePonto:
        ajuste = object.__new__(AjustePonto)
        ajuste.id = self.id
        ajuste.team_id = self.team_id
        ajuste.funcionario_id = self.funcionario_id
        ajuste.data_referencia = self.data_referencia
        ajuste.justificativa = self.justificativa
        ajuste.hora_entrada_solicitada = self.hora_entrada_solicitada
        ajuste.hora_saida_solicitada = self.hora_saida_solicitada
        ajuste.status = StatusAjuste(self.status)
        ajuste.motivo_rejeicao = self.motivo_rejeicao
        ajuste.created_at = self.created_at
        ajuste.is_deleted = self.is_deleted
        return ajuste

    @classmethod
    def from_domain(cls, ajuste: AjustePonto) -> "AjustePontoModel":
        return cls(
            id=ajuste.id or uuid.uuid4(),
            team_id=ajuste.team_id,
            funcionario_id=ajuste.funcionario_id,
            data_referencia=ajuste.data_referencia,
            justificativa=ajuste.justificativa,
            hora_entrada_solicitada=ajuste.hora_entrada_solicitada,
            hora_saida_solicitada=ajuste.hora_saida_solicitada,
            status=ajuste.status.value,
            motivo_rejeicao=ajuste.motivo_rejeicao,
            is_deleted=ajuste.is_deleted,
        )

    def update_from_domain(self, ajuste: AjustePonto) -> None:
        self.data_referencia = ajuste.data_referencia
        self.justificativa = ajuste.justificativa
        self.hora_entrada_solicitada = ajuste.hora_entrada_solicitada
        self.hora_saida_solicitada = ajuste.hora_saida_solicitada
        self.status = ajuste.status.value
        self.motivo_rejeicao = ajuste.motivo_rejeicao
        self.is_deleted = ajuste.is_deleted


class TipoAtestadoModel(Base, TimestampMixin):
    __tablename__ = "rh_tipos_atestado"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    prazo_entrega_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    abona_falta: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    descricao: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_rh_tipos_atestado_team_deleted", "team_id", "is_deleted"),
    )

    def to_domain(self) -> TipoAtestado:
        tipo_atestado = object.__new__(TipoAtestado)
        tipo_atestado.id = self.id
        tipo_atestado.team_id = self.team_id
        tipo_atestado.nome = self.nome
        tipo_atestado.prazo_entrega_dias = self.prazo_entrega_dias
        tipo_atestado.abona_falta = self.abona_falta
        tipo_atestado.descricao = self.descricao
        tipo_atestado.is_deleted = self.is_deleted
        return tipo_atestado

    @classmethod
    def from_domain(cls, tipo_atestado: TipoAtestado) -> "TipoAtestadoModel":
        return cls(
            id=tipo_atestado.id or uuid.uuid4(),
            team_id=tipo_atestado.team_id,
            nome=tipo_atestado.nome,
            prazo_entrega_dias=tipo_atestado.prazo_entrega_dias,
            abona_falta=tipo_atestado.abona_falta,
            descricao=tipo_atestado.descricao,
            is_deleted=tipo_atestado.is_deleted,
        )

    def update_from_domain(self, tipo_atestado: TipoAtestado) -> None:
        self.nome = tipo_atestado.nome
        self.prazo_entrega_dias = tipo_atestado.prazo_entrega_dias
        self.abona_falta = tipo_atestado.abona_falta
        self.descricao = tipo_atestado.descricao
        self.is_deleted = tipo_atestado.is_deleted


class AtestadoModel(Base, TimestampMixin):
    __tablename__ = "rh_atestados"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    funcionario_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False)
    tipo_atestado_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_tipos_atestado.id", ondelete="RESTRICT"), nullable=False)
    data_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_fim: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=StatusAtestado.AGUARDANDO_ENTREGA.value)
    motivo_rejeicao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_rh_atestados_team_funcionario_status_periodo", "team_id", "funcionario_id", "status", "data_inicio", "data_fim"),
        Index("idx_rh_atestados_team_status_created", "team_id", "status", "created_at"),
    )

    def to_domain(self) -> Atestado:
        atestado = object.__new__(Atestado)
        atestado.id = self.id
        atestado.team_id = self.team_id
        atestado.funcionario_id = self.funcionario_id
        atestado.tipo_atestado_id = self.tipo_atestado_id
        atestado.data_inicio = self.data_inicio
        atestado.data_fim = self.data_fim
        atestado.file_path = self.file_path
        atestado.status = StatusAtestado(self.status)
        atestado.motivo_rejeicao = self.motivo_rejeicao
        atestado.created_at = self.created_at
        atestado.is_deleted = self.is_deleted
        return atestado

    @classmethod
    def from_domain(cls, atestado: Atestado) -> "AtestadoModel":
        return cls(
            id=atestado.id or uuid.uuid4(),
            team_id=atestado.team_id,
            funcionario_id=atestado.funcionario_id,
            tipo_atestado_id=atestado.tipo_atestado_id,
            data_inicio=atestado.data_inicio,
            data_fim=atestado.data_fim,
            file_path=atestado.file_path,
            status=atestado.status.value,
            motivo_rejeicao=atestado.motivo_rejeicao,
            is_deleted=atestado.is_deleted,
        )

    def update_from_domain(self, atestado: Atestado) -> None:
        self.data_inicio = atestado.data_inicio
        self.data_fim = atestado.data_fim
        self.file_path = atestado.file_path
        self.status = atestado.status.value
        self.motivo_rejeicao = atestado.motivo_rejeicao
        self.is_deleted = atestado.is_deleted


class HoleriteModel(Base, TimestampMixin):
    __tablename__ = "rh_holerites"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    funcionario_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False)
    mes_referencia: Mapped[int] = mapped_column(Integer, nullable=False)
    ano_referencia: Mapped[int] = mapped_column(Integer, nullable=False)
    salario_base_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    salario_base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    horas_extras_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    horas_extras_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    descontos_falta_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    descontos_falta_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    acrescimos_manuais_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    acrescimos_manuais_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    descontos_manuais_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    descontos_manuais_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    valor_liquido_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    valor_liquido_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StatusHolerite.RASCUNHO.value)
    pagamento_agendado_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pagamentos_agendados.id", ondelete="SET NULL"), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index(
            "uq_rh_holerites_team_funcionario_competencia_active",
            "team_id",
            "funcionario_id",
            "mes_referencia",
            "ano_referencia",
            unique=True,
            postgresql_where=((is_deleted == False) & (status != StatusHolerite.CANCELADO.value)),  # noqa: E712
        ),
        Index("idx_rh_holerites_team_competencia_status", "team_id", "mes_referencia", "ano_referencia", "status"),
    )

    def to_domain(self) -> Holerite:
        holerite = object.__new__(Holerite)
        holerite.id = self.id
        holerite.team_id = self.team_id
        holerite.funcionario_id = self.funcionario_id
        holerite.mes_referencia = self.mes_referencia
        holerite.ano_referencia = self.ano_referencia
        holerite.salario_base = Money(self.salario_base_amount, self.salario_base_currency)
        holerite.horas_extras = Money(self.horas_extras_amount, self.horas_extras_currency)
        holerite.descontos_falta = Money(self.descontos_falta_amount, self.descontos_falta_currency)
        holerite.acrescimos_manuais = Money(self.acrescimos_manuais_amount, self.acrescimos_manuais_currency)
        holerite.descontos_manuais = Money(self.descontos_manuais_amount, self.descontos_manuais_currency)
        holerite.valor_liquido = Money(self.valor_liquido_amount, self.valor_liquido_currency)
        holerite.status = StatusHolerite(self.status)
        holerite.pagamento_agendado_id = self.pagamento_agendado_id
        holerite.is_deleted = self.is_deleted
        return holerite

    @classmethod
    def from_domain(cls, holerite: Holerite) -> "HoleriteModel":
        return cls(
            id=holerite.id or uuid.uuid4(),
            team_id=holerite.team_id,
            funcionario_id=holerite.funcionario_id,
            mes_referencia=holerite.mes_referencia,
            ano_referencia=holerite.ano_referencia,
            salario_base_amount=holerite.salario_base.amount,
            salario_base_currency=holerite.salario_base.currency,
            horas_extras_amount=holerite.horas_extras.amount,
            horas_extras_currency=holerite.horas_extras.currency,
            descontos_falta_amount=holerite.descontos_falta.amount,
            descontos_falta_currency=holerite.descontos_falta.currency,
            acrescimos_manuais_amount=holerite.acrescimos_manuais.amount,
            acrescimos_manuais_currency=holerite.acrescimos_manuais.currency,
            descontos_manuais_amount=holerite.descontos_manuais.amount,
            descontos_manuais_currency=holerite.descontos_manuais.currency,
            valor_liquido_amount=holerite.valor_liquido.amount,
            valor_liquido_currency=holerite.valor_liquido.currency,
            status=holerite.status.value,
            pagamento_agendado_id=holerite.pagamento_agendado_id,
            is_deleted=holerite.is_deleted,
        )

    def update_from_domain(self, holerite: Holerite) -> None:
        self.mes_referencia = holerite.mes_referencia
        self.ano_referencia = holerite.ano_referencia
        self.salario_base_amount = holerite.salario_base.amount
        self.salario_base_currency = holerite.salario_base.currency
        self.horas_extras_amount = holerite.horas_extras.amount
        self.horas_extras_currency = holerite.horas_extras.currency
        self.descontos_falta_amount = holerite.descontos_falta.amount
        self.descontos_falta_currency = holerite.descontos_falta.currency
        self.acrescimos_manuais_amount = holerite.acrescimos_manuais.amount
        self.acrescimos_manuais_currency = holerite.acrescimos_manuais.currency
        self.descontos_manuais_amount = holerite.descontos_manuais.amount
        self.descontos_manuais_currency = holerite.descontos_manuais.currency
        self.valor_liquido_amount = holerite.valor_liquido.amount
        self.valor_liquido_currency = holerite.valor_liquido.currency
        self.status = holerite.status.value
        self.pagamento_agendado_id = holerite.pagamento_agendado_id
        self.is_deleted = holerite.is_deleted


class RhAuditLogModel(Base):
    __tablename__ = "rh_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_rh_audit_logs_team_entity_created", "team_id", "entity_type", "entity_id", "created_at"),
        Index("idx_rh_audit_logs_team_actor_created", "team_id", "actor_user_id", "created_at"),
    )

    def to_domain(self) -> RhAuditLog:
        audit_log = object.__new__(RhAuditLog)
        audit_log.id = self.id
        audit_log.team_id = self.team_id
        audit_log.actor_user_id = self.actor_user_id
        audit_log.actor_role = self.actor_role
        audit_log.entity_type = self.entity_type
        audit_log.entity_id = self.entity_id
        audit_log.action = self.action
        audit_log.before = self.before
        audit_log.after = self.after
        audit_log.reason = self.reason
        audit_log.request_id = self.request_id
        audit_log.ip_hash = self.ip_hash
        audit_log.user_agent = self.user_agent
        audit_log.created_at = self.created_at
        return audit_log

    @classmethod
    def from_domain(cls, audit_log: RhAuditLog) -> "RhAuditLogModel":
        return cls(
            id=audit_log.id or uuid.uuid4(),
            team_id=audit_log.team_id,
            actor_user_id=audit_log.actor_user_id,
            actor_role=audit_log.actor_role,
            entity_type=audit_log.entity_type,
            entity_id=audit_log.entity_id,
            action=audit_log.action,
            before=audit_log.before,
            after=audit_log.after,
            reason=audit_log.reason,
            request_id=audit_log.request_id,
            ip_hash=audit_log.ip_hash,
            user_agent=audit_log.user_agent,
            created_at=audit_log.created_at,
        )


class RhIdempotencyKeyModel(Base):
    __tablename__ = "rh_idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("uq_rh_idempotency_keys_team_scope_key", "team_id", "scope", "key", unique=True),
    )

    def to_domain(self) -> RhIdempotencyKey:
        idempotency_key = object.__new__(RhIdempotencyKey)
        idempotency_key.id = self.id
        idempotency_key.team_id = self.team_id
        idempotency_key.scope = self.scope
        idempotency_key.key = self.key
        idempotency_key.created_at = self.created_at
        return idempotency_key

    @classmethod
    def from_domain(cls, idempotency_key: RhIdempotencyKey) -> "RhIdempotencyKeyModel":
        return cls(
            id=idempotency_key.id or uuid.uuid4(),
            team_id=idempotency_key.team_id,
            scope=idempotency_key.scope,
            key=idempotency_key.key,
            created_at=idempotency_key.created_at,
        )


class RhSalarioHistoricoModel(Base):
    __tablename__ = "rh_salario_historico"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    funcionario_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False)
    salario_anterior_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    salario_anterior_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    salario_novo_amount: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    salario_novo_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_domain(self) -> RhSalarioHistorico:
        historico = object.__new__(RhSalarioHistorico)
        historico.id = self.id
        historico.team_id = self.team_id
        historico.funcionario_id = self.funcionario_id
        historico.salario_anterior = Money(self.salario_anterior_amount, self.salario_anterior_currency)
        historico.salario_novo = Money(self.salario_novo_amount, self.salario_novo_currency)
        historico.changed_by_user_id = self.changed_by_user_id
        historico.reason = self.reason
        historico.created_at = self.created_at
        return historico
