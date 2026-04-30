from __future__ import annotations

from calendar import monthrange
from datetime import datetime, time, timezone

import structlog

from app.application.dtos.rh import (
    RhAuditLogFiltersDTO,
    RhAuditLogListItemDTO,
    RhDashboardSummaryDTO,
    RhMeResumoDTO,
    RhUltimoHoleriteFechadoDTO,
    RhUltimoPontoDTO,
)
from app.application.providers.repo.rh_repo import (
    AjustePontoRepository,
    AtestadoRepository,
    FeriasRepository,
    FuncionarioRepository,
    HoleriteRepository,
    RegistroPontoRepository,
    RhAuditLogRepository,
)
from app.application.providers.uow import UOWProvider
from app.application.services.rh_audit_service import RhAuditService
from app.domain.entities.rh import RhAuditLog, StatusAjuste, StatusAtestado, StatusFerias, StatusHolerite, StatusPonto
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError

logger = structlog.get_logger()


class RhDashboardService:
    def __init__(
        self,
        funcionario_repo: FuncionarioRepository,
        ajuste_repo: AjustePontoRepository,
        ferias_repo: FeriasRepository,
        atestado_repo: AtestadoRepository,
        registro_ponto_repo: RegistroPontoRepository,
        holerite_repo: HoleriteRepository,
        audit_repo: RhAuditLogRepository,
        uow: UOWProvider,
    ) -> None:
        self.funcionario_repo = funcionario_repo
        self.ajuste_repo = ajuste_repo
        self.ferias_repo = ferias_repo
        self.atestado_repo = atestado_repo
        self.registro_ponto_repo = registro_ponto_repo
        self.holerite_repo = holerite_repo
        self.audit_repo = audit_repo
        self.uow = uow

    async def obter_dashboard(self, current_user: User, mes: int, ano: int) -> RhDashboardSummaryDTO:
        self._ensure_rh_admin(current_user)
        self._validate_competencia(mes, ano)
        team_id = current_user.team.id
        start, end = self._competencia_bounds(mes, ano)
        now = datetime.now(timezone.utc)
        day_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
        day_end = datetime.combine(now.date(), time.max, tzinfo=timezone.utc)

        total_funcionarios_ativos = await self.funcionario_repo.count_by_team(team_id, is_active=True)
        ajustes_pendentes = await self.ajuste_repo.count_by_filters(team_id, status=StatusAjuste.PENDENTE)
        ferias_em_andamento = await self.ferias_repo.count_by_filters(
            team_id,
            status=StatusFerias.EM_ANDAMENTO,
            start=day_start,
            end=day_end,
        )
        atestados_aguardando = await self.atestado_repo.count_by_filters(team_id, status=StatusAtestado.AGUARDANDO_ENTREGA)
        atestados_vencidos = await self.atestado_repo.count_by_filters(team_id, status=StatusAtestado.VENCIDO)
        pontos_negados_periodo = await self.registro_ponto_repo.count_by_team_periodo(team_id, start, end, status=StatusPonto.NEGADO)
        pontos_inconsistentes_periodo = await self.registro_ponto_repo.count_by_team_periodo(
            team_id,
            start,
            end,
            status=StatusPonto.INCONSISTENTE,
        )
        holerite_summary = await self.holerite_repo.summarize_by_competencia(team_id, mes, ano)

        await self._record_event(current_user, "rh.dashboard.viewed", entity_type="dashboard")
        logger.info(
            "rh.dashboard.viewed",
            team_id=str(team_id),
            user_id=str(current_user.id),
            mes=mes,
            ano=ano,
            ajustes_pendentes=ajustes_pendentes,
            atestados_aguardando=atestados_aguardando,
        )

        return RhDashboardSummaryDTO(
            mes=mes,
            ano=ano,
            total_funcionarios_ativos=total_funcionarios_ativos,
            ajustes_pendentes=ajustes_pendentes,
            ferias_em_andamento=ferias_em_andamento,
            atestados_aguardando=atestados_aguardando,
            atestados_vencidos=atestados_vencidos,
            pontos_negados_periodo=pontos_negados_periodo,
            pontos_inconsistentes_periodo=pontos_inconsistentes_periodo,
            holerites_rascunho=holerite_summary.get(StatusHolerite.RASCUNHO.value, 0),
            holerites_fechados=holerite_summary.get(StatusHolerite.FECHADO.value, 0),
            total_liquido_competencia=holerite_summary.get("total_liquido", 0),
        )

    async def obter_meu_resumo(self, current_user: User) -> RhMeResumoDTO:
        team_id = current_user.team.id
        funcionario = await self.funcionario_repo.get_by_user_id(team_id, current_user.id)
        if funcionario is None or funcionario.is_deleted or not funcionario.is_active:
            raise DomainError("Funcionario vinculado nao encontrado")

        start = datetime(2000, 1, 1, tzinfo=timezone.utc)
        end = datetime(2100, 1, 1, tzinfo=timezone.utc)
        ultimo_ponto_items = await self.registro_ponto_repo.list_by_funcionario_periodo(
            team_id,
            funcionario.id,
            start,
            end,
            page=1,
            limit=1,
        )
        ultimo_holerite = None
        holerites = await self.holerite_repo.list_by_funcionario(team_id, funcionario.id, page=1, limit=20)
        for item in holerites:
            if item.status == StatusHolerite.FECHADO:
                ultimo_holerite = item
                break

        ajustes_pendentes = await self.ajuste_repo.count_by_filters(
            team_id,
            funcionario_id=funcionario.id,
            status=StatusAjuste.PENDENTE,
        )
        ferias_pendentes = await self.ferias_repo.count_by_filters(
            team_id,
            funcionario_id=funcionario.id,
            status=StatusFerias.SOLICITADO,
        )
        atestados_pendentes = await self.atestado_repo.count_by_filters(
            team_id,
            funcionario_id=funcionario.id,
            status=StatusAtestado.AGUARDANDO_ENTREGA,
        )

        await self._record_event(current_user, "rh.employee_area.accessed", entity_type="employee_area")
        logger.info(
            "rh.employee_area.accessed",
            team_id=str(team_id),
            user_id=str(current_user.id),
            funcionario_id=str(funcionario.id),
            ajustes_pendentes=ajustes_pendentes,
            ferias_pendentes=ferias_pendentes,
            atestados_pendentes=atestados_pendentes,
        )

        return RhMeResumoDTO(
            ultimo_ponto=(
                RhUltimoPontoDTO(
                    tipo=ultimo_ponto_items[0].tipo,
                    status=ultimo_ponto_items[0].status,
                    timestamp=ultimo_ponto_items[0].timestamp,
                )
                if ultimo_ponto_items
                else None
            ),
            ajustes_pendentes=ajustes_pendentes,
            ferias_pendentes=ferias_pendentes,
            atestados_pendentes=atestados_pendentes,
            ultimo_holerite_fechado=(
                RhUltimoHoleriteFechadoDTO(
                    mes_referencia=ultimo_holerite.mes_referencia,
                    ano_referencia=ultimo_holerite.ano_referencia,
                    valor_liquido=ultimo_holerite.valor_liquido.amount,
                    status=ultimo_holerite.status,
                )
                if ultimo_holerite is not None
                else None
            ),
        )

    async def obter_meu_vinculo(self, current_user: User) -> dict:
        funcionario = await self.funcionario_repo.get_by_user_id(current_user.team.id, current_user.id)
        if funcionario is None or funcionario.is_deleted or not funcionario.is_active:
            return {"vinculado": False, "funcionario_id": None, "funcionario_nome": None}
        return {
            "vinculado": True,
            "funcionario_id": str(funcionario.id),
            "funcionario_nome": funcionario.nome,
        }

    async def listar_audit_logs(
        self,
        current_user: User,
        page: int,
        limit: int,
        filters: RhAuditLogFiltersDTO | dict,
    ) -> tuple[list[RhAuditLogListItemDTO], int]:
        self._ensure_rh_admin(current_user)
        team_id = current_user.team.id
        if isinstance(filters, dict):
            filters = RhAuditLogFiltersDTO(**filters)

        items = await self.audit_repo.list_by_filters(team_id, page, limit, **filters.model_dump(exclude_none=True))
        total = await self.audit_repo.count_by_filters(team_id, **filters.model_dump(exclude_none=True))

        await self._record_event(current_user, "rh.audit_logs.viewed", entity_type="audit_log")
        logger.info(
            "rh.audit_logs.viewed",
            team_id=str(team_id),
            user_id=str(current_user.id),
            page=page,
            limit=limit,
            total=total,
            filters=filters.model_dump(exclude_none=True),
        )

        return [
            RhAuditLogListItemDTO(
                id=item.id,
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                action=item.action,
                actor_user_id=item.actor_user_id,
                actor_role=item.actor_role,
                reason=item.reason,
                before=RhAuditService._mask_dict(item.before),
                after=RhAuditService._mask_dict(item.after),
                request_id=item.request_id,
                ip_hash=item.ip_hash,
                user_agent=item.user_agent,
                created_at=item.created_at,
            )
            for item in items
        ], total

    async def _record_event(self, current_user: User, action: str, entity_type: str) -> None:
        await self.audit_repo.save(
            RhAuditLog(
                team_id=current_user.team.id,
                actor_user_id=current_user.id,
                actor_role=current_user.role.value,
                entity_type=entity_type,
                entity_id=None,
                action=action,
            )
        )
        await self.uow.commit()

    def _ensure_rh_admin(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")

    def _validate_competencia(self, mes: int, ano: int) -> None:
        if mes < 1 or mes > 12:
            raise DomainError("Mes de referencia invalido")
        if ano <= 0:
            raise DomainError("Ano de referencia invalido")

    def _competencia_bounds(self, mes: int, ano: int) -> tuple[datetime, datetime]:
        last_day = monthrange(ano, mes)[1]
        return (
            datetime(ano, mes, 1, 0, 0, tzinfo=timezone.utc),
            datetime(ano, mes, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc),
        )
