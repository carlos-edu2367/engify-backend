from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import structlog

from app.application.dtos.rh import (
    RhEstadoPonto7DiasDTO,
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
    EventoCalendarioRepository,
    FeriasRepository,
    FuncionarioRepository,
    HorarioTrabalhoRepository,
    HoleriteRepository,
    RegistroPontoRepository,
    RhAuditLogRepository,
)
from app.application.providers.uow import UOWProvider
from app.application.services.rh_audit_service import RhAuditService
from app.domain.entities.rh import HorarioTrabalho, RegistroPonto, RhAuditLog, StatusAjuste, StatusAtestado, StatusFerias, StatusHolerite, StatusPonto, TurnoHorario
from app.domain.entities.rh_calendario import EventoCalendarioRh, TipoEventoCalendario
from app.domain.services.rh_ponto_calculo import minutos_liberacao, resumir_periodo
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError

logger = structlog.get_logger()


class RhDashboardService:
    def __init__(
        self,
        funcionario_repo: FuncionarioRepository,
        horario_repo: HorarioTrabalhoRepository,
        ajuste_repo: AjustePontoRepository,
        ferias_repo: FeriasRepository,
        atestado_repo: AtestadoRepository,
        registro_ponto_repo: RegistroPontoRepository,
        holerite_repo: HoleriteRepository,
        audit_repo: RhAuditLogRepository,
        uow: UOWProvider,
        evento_calendario_repo: EventoCalendarioRepository | None = None,
    ) -> None:
        self.funcionario_repo = funcionario_repo
        self.horario_repo = horario_repo
        self.ajuste_repo = ajuste_repo
        self.ferias_repo = ferias_repo
        self.atestado_repo = atestado_repo
        self.registro_ponto_repo = registro_ponto_repo
        self.holerite_repo = holerite_repo
        self.audit_repo = audit_repo
        self.uow = uow
        self.evento_calendario_repo = evento_calendario_repo

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
        estado_ponto_7_dias = await self._calcular_estado_ponto_7_dias(team_id, funcionario.id)

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
            estado_ponto_7_dias=estado_ponto_7_dias,
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

    async def _calcular_estado_ponto_7_dias(self, team_id, funcionario_id) -> RhEstadoPonto7DiasDTO:
        # A janela termina ONTEM de proposito: incluir o dia em andamento faz o
        # saldo ainda nao cumprido aparecer como horas faltantes durante o
        # proprio expediente. O dia corrente e mostrado no card "Hoje".
        hoje = datetime.now(timezone.utc).date()
        fim = hoje - timedelta(days=1)
        inicio = fim - timedelta(days=6)
        start = datetime.combine(inicio, time.min, tzinfo=timezone.utc)
        end = datetime.combine(fim, time.max, tzinfo=timezone.utc)
        horario = await self.horario_repo.get_by_funcionario_id(team_id, funcionario_id)
        registros = await self.registro_ponto_repo.list_by_funcionario_periodo(
            team_id,
            funcionario_id,
            start,
            end,
            page=1,
            limit=500,
        )
        eventos_calendario = (
            await self.evento_calendario_repo.list_by_periodo(team_id, inicio, fim)
            if self.evento_calendario_repo is not None
            else []
        )
        return self._summarize_estado_ponto_7_dias(inicio, fim, horario, registros, funcionario_id, eventos_calendario)

    def _summarize_estado_ponto_7_dias(
        self,
        inicio: date,
        fim: date,
        horario: HorarioTrabalho | None,
        registros: list[RegistroPonto],
        funcionario_id=None,
        eventos_calendario: list[EventoCalendarioRh] | None = None,
    ) -> RhEstadoPonto7DiasDTO:
        if horario is None:
            def turno_para_dia(_weekday: int) -> TurnoHorario | None:
                return None
        else:
            turno_para_dia = horario.turno_para_dia

        datas_abonadas: set = set()
        liberacoes: dict = {}
        for evento in eventos_calendario or []:
            if not evento.aplica_a(funcionario_id):
                continue
            if evento.tipo in {TipoEventoCalendario.FERIADO, TipoEventoCalendario.PONTO_FACULTATIVO, TipoEventoCalendario.ABONO}:
                datas_abonadas.add(evento.data)
            elif evento.tipo == TipoEventoCalendario.LIBERACAO_ANTECIPADA and horario is not None:
                turno_dia = horario.turno_para_dia(evento.data.weekday())
                if turno_dia is not None:
                    liberacoes[evento.data] = minutos_liberacao(turno_dia, evento.hora_corte)

        resumo = resumir_periodo(
            registros=registros,
            turno_para_dia=turno_para_dia,
            inicio=inicio,
            fim=fim,
            datas_abonadas=datas_abonadas,
            liberacoes=liberacoes,
        )
        return RhEstadoPonto7DiasDTO(
            inicio=inicio,
            fim=fim,
            faltas=resumo.faltas,
            horas_extras=(resumo.extra_min / Decimal("60")).quantize(Decimal("0.01")),
            horas_faltantes=(resumo.falta_min / Decimal("60")).quantize(Decimal("0.01")),
            pontos_inconsistentes=resumo.pontos_inconsistentes,
        )
