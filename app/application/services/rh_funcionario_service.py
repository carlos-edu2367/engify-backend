from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.application.dtos.rh import CreateFuncionarioDTO, ReplaceHorarioTrabalhoDTO, UpdateFuncionarioDTO
from app.application.providers.repo.rh_repo import (
    FuncionarioRepository,
    HorarioTrabalhoRepository,
    RhAuditLogRepository,
    RhSalarioHistoricoRepository,
)
from app.application.providers.repo.user_repos import UserRepository
from app.application.providers.uow import UOWProvider
from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import Funcionario, HorarioTrabalho, IntervaloHorario, RhAuditLog, RhSalarioHistorico, TurnoHorario
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError


class RhFuncionarioService:
    def __init__(
        self,
        funcionario_repo: FuncionarioRepository,
        horario_repo: HorarioTrabalhoRepository,
        user_repo: UserRepository,
        audit_repo: RhAuditLogRepository,
        salario_historico_repo: RhSalarioHistoricoRepository,
        uow: UOWProvider,
    ) -> None:
        self.funcionario_repo = funcionario_repo
        self.horario_repo = horario_repo
        self.user_repo = user_repo
        self.audit_repo = audit_repo
        self.salario_historico_repo = salario_historico_repo
        self.uow = uow

    async def create_funcionario(self, dto: CreateFuncionarioDTO, current_user: User) -> Funcionario:
        self._ensure_rh_admin(current_user)
        team_id = current_user.team.id
        cpf = CPF(dto.cpf)
        await self._ensure_cpf_available(team_id, cpf.value)
        await self._validate_user_link(team_id, dto.user_id)

        funcionario = Funcionario(
            team_id=team_id,
            nome=dto.nome,
            cpf=cpf,
            cargo=dto.cargo,
            salario_base=Money(Decimal(dto.salario_base)),
            data_admissao=self._as_utc_datetime(dto.data_admissao),
            user_id=dto.user_id,
        )
        horario = HorarioTrabalho(
            team_id=team_id,
            funcionario_id=funcionario.id,
            turnos=self._build_turnos(dto.horario_trabalho),
        )

        await self.funcionario_repo.save(funcionario)
        await self.horario_repo.save(horario)
        await self._record_audit(
            current_user=current_user,
            entity_type="funcionario",
            entity_id=funcionario.id,
            action="rh.funcionario.created",
            after=self._funcionario_snapshot(funcionario),
        )
        await self.uow.commit()

        funcionario.horario_trabalho = horario
        return funcionario

    async def list_funcionarios(
        self,
        current_user: User,
        page: int,
        limit: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Funcionario], int]:
        self._ensure_rh_admin(current_user)
        team_id = current_user.team.id
        items = await self.funcionario_repo.list_by_team(team_id, page, limit, search=search, is_active=is_active)
        total = await self.funcionario_repo.count_by_team(team_id, search=search, is_active=is_active)
        return items, total

    async def get_funcionario(self, funcionario_id: UUID, current_user: User) -> Funcionario:
        self._ensure_rh_admin(current_user)
        funcionario = await self.funcionario_repo.get_by_id(funcionario_id, current_user.team.id)
        funcionario.horario_trabalho = await self.horario_repo.get_by_funcionario_id(current_user.team.id, funcionario.id)
        return funcionario

    async def update_funcionario(
        self,
        funcionario_id: UUID,
        dto: UpdateFuncionarioDTO,
        current_user: User,
        reason: str | None = None,
    ) -> Funcionario:
        self._ensure_rh_admin(current_user)
        team_id = current_user.team.id
        funcionario = await self.funcionario_repo.get_by_id(funcionario_id, team_id)
        before = self._funcionario_snapshot(funcionario)

        if dto.cpf is not None:
            cpf = CPF(dto.cpf)
            existing = await self.funcionario_repo.get_by_cpf(team_id, cpf.value)
            if existing and existing.id != funcionario.id:
                raise DomainError("Ja existe um funcionario com esse CPF neste time")
            funcionario.cpf = cpf
        if dto.user_id is not None and dto.user_id != funcionario.user_id:
            await self._validate_user_link(team_id, dto.user_id, existing_funcionario_id=funcionario.id)
            funcionario.user_id = dto.user_id
        if dto.nome is not None:
            if not dto.nome.strip():
                raise DomainError("Nome do funcionario e obrigatorio")
            funcionario.nome = dto.nome
        if dto.cargo is not None:
            if not dto.cargo.strip():
                raise DomainError("Cargo do funcionario e obrigatorio")
            funcionario.cargo = dto.cargo
        if dto.salario_base is not None:
            novo_salario = Money(Decimal(dto.salario_base))
            if novo_salario.amount != funcionario.salario_base.amount:
                if not (reason or "").strip():
                    raise DomainError("Motivo da alteracao salarial e obrigatorio")
                await self.salario_historico_repo.save(
                    RhSalarioHistorico(
                        team_id=team_id,
                        funcionario_id=funcionario.id,
                        salario_anterior=funcionario.salario_base,
                        salario_novo=novo_salario,
                        changed_by_user_id=current_user.id,
                        reason=reason,
                    )
                )
                funcionario.salario_base = novo_salario
        if dto.data_admissao is not None:
            funcionario.data_admissao = self._as_utc_datetime(dto.data_admissao)
        if dto.is_active is not None:
            funcionario.is_active = dto.is_active

        saved = await self.funcionario_repo.save(funcionario)
        await self._record_audit(
            current_user=current_user,
            entity_type="funcionario",
            entity_id=saved.id,
            action="rh.funcionario.updated",
            before=before,
            after=self._funcionario_snapshot(saved),
            reason=reason,
        )
        await self.uow.commit()
        saved.horario_trabalho = await self.horario_repo.get_by_funcionario_id(team_id, saved.id)
        return saved

    async def delete_funcionario(
        self,
        funcionario_id: UUID,
        current_user: User,
        reason: str | None = None,
    ) -> None:
        self._ensure_rh_admin(current_user)
        team_id = current_user.team.id
        funcionario = await self.funcionario_repo.get_by_id(funcionario_id, team_id)
        horario = await self.horario_repo.get_by_funcionario_id(team_id, funcionario_id)
        before = self._funcionario_snapshot(funcionario)

        funcionario.delete()
        await self.funcionario_repo.save(funcionario)
        if horario is not None:
            horario.delete()
            await self.horario_repo.save(horario)

        await self._record_audit(
            current_user=current_user,
            entity_type="funcionario",
            entity_id=funcionario.id,
            action="rh.funcionario.deleted",
            before=before,
            reason=reason,
        )
        await self.uow.commit()

    async def replace_horario(
        self,
        funcionario_id: UUID,
        dto: ReplaceHorarioTrabalhoDTO,
        current_user: User,
    ) -> HorarioTrabalho:
        self._ensure_rh_admin(current_user)
        team_id = current_user.team.id
        await self.funcionario_repo.get_by_id(funcionario_id, team_id)
        existing = await self.horario_repo.get_by_funcionario_id(team_id, funcionario_id)

        if existing is None:
            horario = HorarioTrabalho(
                team_id=team_id,
                funcionario_id=funcionario_id,
                turnos=self._build_turnos(dto.turnos),
            )
            action = "rh.horario.created"
            before = None
        else:
            before = self._horario_snapshot(existing)
            horario = HorarioTrabalho(
                team_id=team_id,
                funcionario_id=funcionario_id,
                turnos=self._build_turnos(dto.turnos),
                id=existing.id,
            )
            action = "rh.horario.updated"

        saved = await self.horario_repo.save(horario)
        await self._record_audit(
            current_user=current_user,
            entity_type="horario_trabalho",
            entity_id=saved.id,
            action=action,
            before=before,
            after=self._horario_snapshot(saved),
        )
        await self.uow.commit()
        return saved

    async def get_horario(self, funcionario_id: UUID, current_user: User) -> HorarioTrabalho:
        self._ensure_rh_admin(current_user)
        await self.funcionario_repo.get_by_id(funcionario_id, current_user.team.id)
        horario = await self.horario_repo.get_by_funcionario_id(current_user.team.id, funcionario_id)
        if horario is None:
            raise DomainError("Horario de trabalho nao encontrado")
        return horario

    def _ensure_rh_admin(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")

    async def _ensure_cpf_available(self, team_id: UUID, cpf: str) -> None:
        existing = await self.funcionario_repo.get_by_cpf(team_id, cpf)
        if existing:
            raise DomainError("Ja existe um funcionario com esse CPF neste time")

    async def _validate_user_link(
        self,
        team_id: UUID,
        user_id: UUID | None,
        existing_funcionario_id: UUID | None = None,
    ) -> None:
        if user_id is None:
            return
        user = await self.user_repo.get_by_id(user_id)
        if user.team.id != team_id:
            raise DomainError("Usuario nao encontrado")
        linked = await self.funcionario_repo.get_by_user_id(team_id, user_id)
        if linked and linked.id != existing_funcionario_id:
            raise DomainError("Este usuario ja esta vinculado a outro funcionario ativo")

    def _build_turnos(self, turnos_dto) -> list[TurnoHorario]:
        return [
            TurnoHorario(
                dia_semana=turno.dia_semana,
                hora_entrada=turno.hora_entrada,
                hora_saida=turno.hora_saida,
                intervalos=[
                    IntervaloHorario(
                        hora_inicio=intervalo.hora_inicio,
                        hora_fim=intervalo.hora_fim,
                    )
                    for intervalo in turno.intervalos
                ],
            )
            for turno in turnos_dto
        ]

    def _as_utc_datetime(self, value) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)

    async def _record_audit(
        self,
        current_user: User,
        entity_type: str,
        entity_id: UUID,
        action: str,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ) -> None:
        event = RhAuditLog(
            team_id=current_user.team.id,
            actor_user_id=current_user.id,
            actor_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before=self._mask_audit_payload(before),
            after=self._mask_audit_payload(after),
            reason=reason,
        )
        await self.audit_repo.save(event)

    def _mask_audit_payload(self, payload: dict | None) -> dict | None:
        if payload is None:
            return None
        masked = dict(payload)
        if "cpf" in masked:
            digits = "".join(ch for ch in str(masked["cpf"]) if ch.isdigit())
            masked["cpf"] = f"***{digits[-4:]}" if digits else "***"
        if "salario_base" in masked:
            masked["salario_base"] = "***"
        return masked

    def _funcionario_snapshot(self, funcionario: Funcionario) -> dict:
        return {
            "nome": funcionario.nome,
            "cpf": funcionario.cpf.value,
            "cargo": funcionario.cargo,
            "salario_base": str(funcionario.salario_base.amount),
            "user_id": str(funcionario.user_id) if funcionario.user_id else None,
            "is_active": funcionario.is_active,
            "is_deleted": funcionario.is_deleted,
        }

    def _horario_snapshot(self, horario: HorarioTrabalho) -> dict:
        return {
            "funcionario_id": str(horario.funcionario_id),
            "turnos": [
                {
                    "dia_semana": turno.dia_semana,
                    "hora_entrada": turno.hora_entrada.isoformat(),
                    "hora_saida": turno.hora_saida.isoformat(),
                    "intervalos": [
                        {
                            "hora_inicio": intervalo.hora_inicio.isoformat(),
                            "hora_fim": intervalo.hora_fim.isoformat(),
                        }
                        for intervalo in turno.intervalos
                    ],
                }
                for turno in horario.turnos
            ],
        }
