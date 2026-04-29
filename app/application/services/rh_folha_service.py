from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from uuid import UUID

from app.application.providers.repo.financeiro_repo import PagamentoAgendadoRepository
from app.application.providers.repo.rh_repo import (
    AtestadoRepository,
    FuncionarioRepository,
    HoleriteRepository,
    HoleriteItemRepository,
    HorarioTrabalhoRepository,
    RegraEncargoRepository,
    RegistroPontoRepository,
    RhAuditLogRepository,
    RhFolhaJobRepository,
    RhIdempotencyKeyRepository,
    TipoAtestadoRepository,
    FeriasRepository,
)
from app.application.providers.utility.rh_encargo_cache import RhEncargoCachePort
from app.application.providers.utility.rh_folha_queue import RhFolhaQueuePort
from app.application.providers.uow import UOWProvider
from app.domain.entities.financeiro import MovClass, PagamentoAgendado
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    Atestado,
    FolhaCalculationContext,
    Ferias,
    Funcionario,
    HoleriteItem,
    HoleriteItemNatureza,
    HoleriteItemTipo,
    Holerite,
    HorarioTrabalho,
    RegistroPonto,
    RhAuditLog,
    RhFolhaJob,
    RhFolhaJobStatus,
    StatusAtestado,
    StatusFerias,
    StatusHolerite,
    StatusRegraEncargo,
    StatusPonto,
    TipoPonto,
    TurnoHorario,
)
from app.domain.services.rh_folha_calculation_engine import FolhaCalculationEngine
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError


class RhFolhaService:
    def __init__(
        self,
        funcionario_repo: FuncionarioRepository,
        horario_repo: HorarioTrabalhoRepository,
        registro_ponto_repo: RegistroPontoRepository,
        ferias_repo: FeriasRepository,
        tipo_atestado_repo: TipoAtestadoRepository,
        atestado_repo: AtestadoRepository,
        holerite_repo: HoleriteRepository,
        holerite_item_repo: HoleriteItemRepository | None,
        regra_encargo_repo: RegraEncargoRepository | None,
        pagamento_repo: PagamentoAgendadoRepository,
        audit_repo: RhAuditLogRepository,
        idempotency_repo: RhIdempotencyKeyRepository | None,
        uow: UOWProvider,
        calculation_engine: FolhaCalculationEngine | None = None,
        folha_job_repo: RhFolhaJobRepository | None = None,
        folha_queue: RhFolhaQueuePort | None = None,
        encargo_cache: RhEncargoCachePort | None = None,
    ) -> None:
        self.funcionario_repo = funcionario_repo
        self.horario_repo = horario_repo
        self.registro_ponto_repo = registro_ponto_repo
        self.ferias_repo = ferias_repo
        self.tipo_atestado_repo = tipo_atestado_repo
        self.atestado_repo = atestado_repo
        self.holerite_repo = holerite_repo
        self.holerite_item_repo = holerite_item_repo
        self.regra_encargo_repo = regra_encargo_repo
        self.pagamento_repo = pagamento_repo
        self.audit_repo = audit_repo
        self.idempotency_repo = idempotency_repo
        self.uow = uow
        self.calculation_engine = calculation_engine or FolhaCalculationEngine()
        self.folha_job_repo = folha_job_repo
        self.folha_queue = folha_queue
        self.encargo_cache = encargo_cache

    async def gerar_rascunho_folha(
        self,
        current_user: User,
        mes: int,
        ano: int,
        funcionario_id: UUID | None = None,
    ) -> list[Holerite]:
        self._ensure_rh_admin(current_user)
        team_id = current_user.team.id
        self._validate_competencia(mes, ano)
        funcionarios = await self._load_funcionarios(team_id, funcionario_id)
        funcionario_ids = [item.id for item in funcionarios]
        horarios = await self.horario_repo.list_by_funcionarios(team_id, funcionario_ids)
        start, end = self._competencia_bounds(mes, ano)
        registros = await self.registro_ponto_repo.list_by_competencia(team_id, funcionario_ids, start, end)
        ferias_items = await self.ferias_repo.list_by_competencia(
            team_id,
            funcionario_ids,
            start,
            end,
            statuses={StatusFerias.APROVADO, StatusFerias.EM_ANDAMENTO},
        )
        atestados = await self.atestado_repo.list_by_competencia(
            team_id,
            funcionario_ids,
            start,
            end,
            statuses={StatusAtestado.ENTREGUE},
        )
        abono_por_atestado = await self._build_atestado_abono_map(atestados)
        registros_por_funcionario = self._group_by_funcionario(registros)
        ferias_por_funcionario = self._group_by_funcionario(ferias_items)
        regras_ativas = await self._load_regras_ativas(team_id, mes, ano)
        holerites: list[Holerite] = []

        for funcionario in funcionarios:
            horario = horarios.get(funcionario.id)
            if horario is None:
                raise DomainError("Funcionario sem horario de trabalho ativo para a competencia")

            existing = await self.holerite_repo.get_by_competencia(team_id, funcionario.id, mes, ano)
            horas_extras, descontos_falta = self._calcular_componentes_folha(
                funcionario=funcionario,
                horario=horario,
                mes=mes,
                ano=ano,
                registros=registros_por_funcionario.get(funcionario.id, []),
                ferias_items=ferias_por_funcionario.get(funcionario.id, []),
                abono_atestado=abono_por_atestado.get(funcionario.id, set()),
            )
            acrescimos = existing.acrescimos_manuais if existing else Money(Decimal("0.00"))
            descontos = existing.descontos_manuais if existing else Money(Decimal("0.00"))

            if existing:
                if existing.status == StatusHolerite.FECHADO:
                    raise DomainError("Holerite fechado nao pode ser recalculado automaticamente")
                existing.salario_base = funcionario.salario_base
                existing.horas_extras = horas_extras
                existing.descontos_falta = descontos_falta
                existing.acrescimos_manuais = acrescimos
                existing.descontos_manuais = descontos
                existing.recalcular_valor_liquido()
                saved = await self.holerite_repo.save(existing)
            else:
                saved = await self.holerite_repo.save(
                    Holerite(
                        team_id=team_id,
                        funcionario_id=funcionario.id,
                        mes_referencia=mes,
                        ano_referencia=ano,
                        salario_base=funcionario.salario_base,
                        horas_extras=horas_extras,
                        descontos_falta=descontos_falta,
                        acrescimos_manuais=acrescimos,
                        descontos_manuais=descontos,
                        valor_liquido=funcionario.salario_base,
                        calculation_version="encargos-v2",
                    )
                )
            await self._sync_holerite_items(saved, regras_ativas)
            saved = await self.holerite_repo.save(saved)
            await self._record_audit(
                current_user=current_user,
                entity_id=saved.id,
                entity_type="holerite",
                action="rh.folha.draft_generated",
                after=self._holerite_snapshot(saved),
            )
            holerites.append(saved)

        await self.uow.commit()
        return holerites

    async def _load_regras_ativas(self, team_id: UUID, mes: int, ano: int):
        if self.regra_encargo_repo is None:
            return []
        if self.encargo_cache is not None:
            cached = await self.encargo_cache.get_active_rules(team_id, ano, mes)
            if cached is not None:
                return cached
        competencia = self._competencia_bounds(mes, ano)[1]
        regras = await self.regra_encargo_repo.list_active_by_competencia(team_id, competencia)
        if self.encargo_cache is not None:
            await self.encargo_cache.set_active_rules(team_id, ano, mes, regras)
        return regras

    async def _sync_holerite_items(self, holerite: Holerite, regras_ativas: list | None = None) -> None:
        if self.holerite_item_repo is None:
            return
        itens_base = self._build_holerite_items(holerite)
        context = self._build_calculation_context(holerite, itens_base)
        regras = list(regras_ativas or [])
        result = self.calculation_engine.apply(context, regras)
        await self.holerite_item_repo.replace_automaticos(holerite.team_id, holerite.id, result.itens)
        holerite.atualizar_totais_por_itens(result.itens)
        holerite.calculation_hash = self._build_calculation_hash(holerite, regras, result.itens)
        holerite.calculation_version = "encargos-v2"
        holerite.calculated_at = datetime.now(timezone.utc)

    def _build_holerite_items(self, holerite: Holerite) -> list[HoleriteItem]:
        itens = [
            HoleriteItem(
                team_id=holerite.team_id,
                holerite_id=holerite.id,
                funcionario_id=holerite.funcionario_id,
                tipo=HoleriteItemTipo.SALARIO_BASE,
                origem="sistema",
                codigo="SALARIO_BASE",
                descricao="Salario Base",
                natureza=HoleriteItemNatureza.PROVENTO,
                ordem=100,
                base=holerite.salario_base,
                valor=holerite.salario_base,
            ),
            HoleriteItem(
                team_id=holerite.team_id,
                holerite_id=holerite.id,
                funcionario_id=holerite.funcionario_id,
                tipo=HoleriteItemTipo.HORA_EXTRA,
                origem="sistema",
                codigo="HORA_EXTRA",
                descricao="Horas Extras",
                natureza=HoleriteItemNatureza.PROVENTO,
                ordem=200,
                base=holerite.horas_extras,
                valor=holerite.horas_extras,
            ),
            HoleriteItem(
                team_id=holerite.team_id,
                holerite_id=holerite.id,
                funcionario_id=holerite.funcionario_id,
                tipo=HoleriteItemTipo.FALTA,
                origem="sistema",
                codigo="FALTA",
                descricao="Desconto por Faltas",
                natureza=HoleriteItemNatureza.DESCONTO,
                ordem=300,
                base=holerite.descontos_falta,
                valor=holerite.descontos_falta,
            ),
        ]
        if holerite.acrescimos_manuais.amount != Decimal("0.00"):
            itens.append(
                HoleriteItem(
                    team_id=holerite.team_id,
                    holerite_id=holerite.id,
                    funcionario_id=holerite.funcionario_id,
                    tipo=HoleriteItemTipo.AJUSTE_MANUAL,
                    origem="manual",
                    codigo="ACRESCIMO_MANUAL",
                    descricao="Acrescimo Manual",
                    natureza=HoleriteItemNatureza.PROVENTO,
                    ordem=400,
                    base=holerite.acrescimos_manuais,
                    valor=holerite.acrescimos_manuais,
                )
            )
        if holerite.descontos_manuais.amount != Decimal("0.00"):
            itens.append(
                HoleriteItem(
                    team_id=holerite.team_id,
                    holerite_id=holerite.id,
                    funcionario_id=holerite.funcionario_id,
                    tipo=HoleriteItemTipo.AJUSTE_MANUAL,
                    origem="manual",
                    codigo="DESCONTO_MANUAL",
                    descricao="Desconto Manual",
                    natureza=HoleriteItemNatureza.DESCONTO,
                    ordem=500,
                    base=holerite.descontos_manuais,
                    valor=holerite.descontos_manuais,
                )
            )
        return itens

    def _build_calculation_context(self, holerite: Holerite, itens_base: list[HoleriteItem]) -> FolhaCalculationContext:
        return FolhaCalculationContext(
            team_id=holerite.team_id,
            holerite_id=holerite.id,
            funcionario_id=holerite.funcionario_id,
            competencia_mes=holerite.mes_referencia,
            competencia_ano=holerite.ano_referencia,
            salario_base=holerite.salario_base,
            horas_extras=holerite.horas_extras,
            descontos_falta=holerite.descontos_falta,
            acrescimos_manuais=holerite.acrescimos_manuais,
            descontos_manuais=holerite.descontos_manuais,
            bruto_antes_encargos=holerite.salario_base + holerite.horas_extras + holerite.acrescimos_manuais - holerite.descontos_falta,
            bruto_antes_irrf=holerite.salario_base + holerite.horas_extras + holerite.acrescimos_manuais - holerite.descontos_falta,
            liquido_parcial=holerite.valor_liquido,
            itens=itens_base,
        )

    async def listar_holerites(
        self,
        current_user: User,
        mes: int,
        ano: int,
        status: StatusHolerite | None,
        page: int,
        limit: int,
        funcionario_id: UUID | None = None,
    ):
        self._ensure_rh_admin(current_user)
        items = await self.holerite_repo.list_by_competencia(
            current_user.team.id,
            mes,
            ano,
            status=status,
            page=page,
            limit=limit,
            funcionario_id=funcionario_id,
        )
        total = await self.holerite_repo.count_by_competencia(
            current_user.team.id,
            mes,
            ano,
            status=status,
            funcionario_id=funcionario_id,
        )
        return items, total

    async def obter_holerite(self, holerite_id: UUID, current_user: User) -> Holerite:
        self._ensure_rh_admin(current_user)
        return await self.holerite_repo.get_by_id(holerite_id, current_user.team.id)

    async def atualizar_ajustes_manuais(
        self,
        holerite_id: UUID,
        acrescimos: Decimal,
        descontos: Decimal,
        current_user: User,
        reason: str,
    ) -> Holerite:
        self._ensure_rh_admin(current_user)
        if not reason.strip():
            raise DomainError("Motivo do ajuste manual e obrigatorio")
        holerite = await self.holerite_repo.get_by_id(holerite_id, current_user.team.id)
        before = self._holerite_snapshot(holerite)
        holerite.atualizar_ajustes_manuais(Money(acrescimos), Money(descontos))
        await self._sync_holerite_items(holerite, await self._load_regras_ativas(current_user.team.id, holerite.mes_referencia, holerite.ano_referencia))
        saved = await self.holerite_repo.save(holerite)
        await self._record_audit(
            current_user=current_user,
            entity_id=saved.id,
            entity_type="holerite",
            action="rh.holerite.manual_adjustment.updated",
            before=before,
            after=self._holerite_snapshot(saved),
            reason=reason,
        )
        await self.uow.commit()
        return saved

    async def fechar_folha(
        self,
        current_user: User,
        mes: int,
        ano: int,
        funcionario_ids: list[UUID] | None = None,
        idempotency_key: str | None = None,
    ) -> list[Holerite]:
        self._ensure_rh_admin(current_user)
        self._validate_competencia(mes, ano)
        team_id = current_user.team.id
        scope = f"rh.folha.fechar:{mes}:{ano}"
        if idempotency_key and self.idempotency_repo is not None:
            exists = await self.idempotency_repo.exists_or_create(team_id, scope, idempotency_key)
            if exists:
                existing = await self.holerite_repo.list_rascunhos_by_competencia(team_id, mes, ano, limit=500, funcionario_ids=funcionario_ids)
                if not existing:
                    items = await self.holerite_repo.list_by_competencia(
                        team_id,
                        mes,
                        ano,
                        status=StatusHolerite.FECHADO,
                        page=1,
                        limit=500,
                        funcionario_id=funcionario_ids[0] if funcionario_ids and len(funcionario_ids) == 1 else None,
                    )
                    if funcionario_ids:
                        items = [item for item in items if item.funcionario_id in funcionario_ids]
                    return items

        holerites = await self.holerite_repo.list_rascunhos_by_competencia(team_id, mes, ano, limit=500, funcionario_ids=funcionario_ids)
        if not holerites:
            existing = await self.holerite_repo.list_by_competencia(
                team_id,
                mes,
                ano,
                status=StatusHolerite.FECHADO,
                page=1,
                limit=500,
                funcionario_id=funcionario_ids[0] if funcionario_ids and len(funcionario_ids) == 1 else None,
            )
            if funcionario_ids:
                existing = [item for item in existing if item.funcionario_id in funcionario_ids]
            if existing:
                return existing
            raise DomainError("Nao ha holerites em rascunho para fechar nesta competencia")

        funcionarios = await self._load_funcionarios(team_id, None)
        funcionarios_by_id = {item.id: item for item in funcionarios}
        closed: list[Holerite] = []
        for holerite in holerites:
            funcionario = funcionarios_by_id.get(holerite.funcionario_id)
            if funcionario is None or not funcionario.is_active or funcionario.is_deleted:
                raise DomainError("Funcionario invalido para fechamento da folha")
            pagamento = await self.pagamento_repo.save(
                PagamentoAgendado(
                    team_id=holerite.team_id,
                    title=f"Folha {mes:02d}/{ano} - {funcionario.nome}",
                    details=f"Competencia {mes:02d}/{ano} - holerite {holerite.id}",
                    valor=holerite.valor_liquido,
                    data_agendada=self._data_agendada_fechamento(mes, ano),
                    classe=MovClass.OPERACIONAL,
                )
            )
            holerite.fechar(pagamento.id)
            saved = await self.holerite_repo.save(holerite)
            await self._record_audit(
                current_user=current_user,
                entity_id=saved.id,
                entity_type="holerite",
                action="rh.holerite.closed",
                after=self._holerite_snapshot(saved),
            )
            closed.append(saved)
        await self.uow.commit()
        return closed

    async def listar_meus_holerites(self, current_user: User, page: int, limit: int):
        self._ensure_funcionario(current_user)
        funcionario = await self.funcionario_repo.get_by_user_id(current_user.team.id, current_user.id)
        if funcionario is None or funcionario.is_deleted:
            raise DomainError("Funcionario vinculado nao encontrado")
        items = await self.holerite_repo.list_by_funcionario(current_user.team.id, funcionario.id, page, limit)
        total = await self.holerite_repo.count_by_funcionario(current_user.team.id, funcionario.id)
        return items, total

    async def obter_meu_holerite(self, holerite_id: UUID, current_user: User) -> Holerite:
        self._ensure_funcionario(current_user)
        funcionario = await self.funcionario_repo.get_by_user_id(current_user.team.id, current_user.id)
        if funcionario is None or funcionario.is_deleted:
            raise DomainError("Funcionario vinculado nao encontrado")
        holerite = await self.holerite_repo.get_by_id(holerite_id, current_user.team.id)
        if holerite.funcionario_id != funcionario.id:
            raise DomainError("Holerite nao encontrado")
        return holerite

    async def criar_job_geracao_folha(
        self,
        current_user: User,
        mes: int,
        ano: int,
        funcionario_ids: list[UUID] | None = None,
    ) -> RhFolhaJob:
        self._ensure_rh_admin(current_user)
        self._validate_competencia(mes, ano)
        if self.folha_job_repo is None or self.folha_queue is None:
            raise DomainError("Fila de folha nao configurada")
        job = RhFolhaJob(
            team_id=current_user.team.id,
            mes=mes,
            ano=ano,
            requested_by_user_id=current_user.id,
            funcionario_ids=funcionario_ids,
        )
        saved = await self.folha_job_repo.save(job)
        await self.folha_queue.enqueue_generate_folha(saved.id)
        await self._record_audit(
            current_user=current_user,
            entity_id=saved.id,
            entity_type="rh_folha_job",
            action="rh.folha.job.created",
            after=self._folha_job_snapshot(saved),
        )
        await self.uow.commit()
        return saved

    async def obter_job_geracao_folha(self, current_user: User, job_id: UUID) -> RhFolhaJob:
        self._ensure_rh_admin(current_user)
        if self.folha_job_repo is None:
            raise DomainError("Repositorio de job de folha nao configurado")
        return await self.folha_job_repo.get_by_id(current_user.team.id, job_id)

    async def processar_job_geracao_folha(self, job_id: UUID) -> RhFolhaJob:
        if self.folha_job_repo is None:
            raise DomainError("Repositorio de job de folha nao configurado")
        job = await self.folha_job_repo.get_by_id_unscoped(job_id)
        funcionarios = await self._load_funcionarios_for_job(job.team_id, job.funcionario_ids)
        job.mark_processing(len(funcionarios))
        await self.folha_job_repo.save(job)

        try:
            for funcionario in funcionarios:
                current_user = self._build_system_user(job.team_id, job.requested_by_user_id)
                try:
                    await self.gerar_rascunho_folha(
                        current_user=current_user,
                        mes=job.mes,
                        ano=job.ano,
                        funcionario_id=funcionario.id,
                    )
                    job.register_success()
                except Exception as exc:
                    job.register_failure(funcionario.id, str(exc))
                await self.folha_job_repo.save(job)
            job.mark_completed()
        except Exception as exc:
            job.mark_failed(str(exc))
            await self.folha_job_repo.save(job)
            await self.uow.commit()
            raise

        await self.folha_job_repo.save(job)
        await self.uow.commit()
        return job

    async def _load_funcionarios(self, team_id: UUID, funcionario_id: UUID | None) -> list[Funcionario]:
        if funcionario_id is not None:
            return [await self.funcionario_repo.get_by_id(funcionario_id, team_id)]
        items: list[Funcionario] = []
        offset = 0
        limit = 200
        while True:
            batch = await self.funcionario_repo.list_active_by_team(team_id, limit, offset)
            if not batch:
                break
            items.extend(batch)
            offset += limit
        return items

    async def _load_funcionarios_for_job(self, team_id: UUID, funcionario_ids: list[UUID] | None) -> list[Funcionario]:
        if funcionario_ids:
            return [await self.funcionario_repo.get_by_id(funcionario_id, team_id) for funcionario_id in funcionario_ids]
        return await self._load_funcionarios(team_id, None)

    async def _build_atestado_abono_map(self, atestados: list[Atestado]) -> dict[UUID, set[date]]:
        grouped: dict[UUID, set[date]] = defaultdict(set)
        tipos_cache: dict[UUID, bool] = {}
        for atestado in atestados:
            if atestado.tipo_atestado_id not in tipos_cache:
                tipo = await self.tipo_atestado_repo.get_by_id(atestado.tipo_atestado_id, atestado.team_id)
                tipos_cache[atestado.tipo_atestado_id] = tipo.abona_falta
            if not tipos_cache[atestado.tipo_atestado_id]:
                continue
            current = atestado.data_inicio.date()
            last = atestado.data_fim.date()
            while current <= last:
                grouped[atestado.funcionario_id].add(current)
                current += timedelta(days=1)
        return grouped

    def _calcular_componentes_folha(
        self,
        funcionario: Funcionario,
        horario: HorarioTrabalho,
        mes: int,
        ano: int,
        registros: list[RegistroPonto],
        ferias_items: list[Ferias],
        abono_atestado: set[date],
    ) -> tuple[Money, Money]:
        registros_por_dia: dict[date, list[RegistroPonto]] = defaultdict(list)
        for registro in registros:
            registros_por_dia[registro.timestamp.astimezone(timezone.utc).date()].append(registro)

        expected_minutes_total = Decimal("0")
        extra_minutes_total = Decimal("0")
        falta_minutes_total = Decimal("0")

        start, end = self._competencia_bounds(mes, ano)
        current = start.date()
        last = end.date()
        while current <= last:
            turno = horario.turno_para_dia(current.weekday())
            if turno is None:
                current += timedelta(days=1)
                continue
            expected_minutes_day = Decimal(str(turno.horas_esperadas)) * Decimal("60")
            expected_minutes_total += expected_minutes_day
            if self._is_date_covered_by_ferias(current, ferias_items) or current in abono_atestado:
                current += timedelta(days=1)
                continue
            worked_minutes = self._worked_minutes_for_day(registros_por_dia.get(current, []), turno)
            if worked_minutes == 0:
                falta_minutes_total += expected_minutes_day
            elif worked_minutes > expected_minutes_day:
                extra_minutes_total += worked_minutes - expected_minutes_day
            current += timedelta(days=1)

        if expected_minutes_total == 0:
            return Money(Decimal("0.00")), Money(Decimal("0.00"))
        minute_rate = funcionario.salario_base.amount / expected_minutes_total
        horas_extras = Money((minute_rate * extra_minutes_total).quantize(Decimal("0.01")))
        descontos_falta = Money((minute_rate * falta_minutes_total).quantize(Decimal("0.01")))
        return horas_extras, descontos_falta

    def _worked_minutes_for_day(self, registros: list[RegistroPonto], turno: TurnoHorario | None = None) -> Decimal:
        if not registros:
            return Decimal("0")
        ordered = sorted(registros, key=lambda item: item.timestamp)
        total = Decimal("0")
        entrada_atual: datetime | None = None
        for registro in ordered:
            if registro.status not in {StatusPonto.VALIDADO, StatusPonto.AJUSTADO}:
                continue
            if registro.tipo == TipoPonto.ENTRADA:
                entrada_atual = registro.timestamp
                continue
            if registro.tipo == TipoPonto.SAIDA and entrada_atual is not None:
                worked_minutes = Decimal(str((registro.timestamp - entrada_atual).total_seconds() / 60))
                if turno is not None:
                    worked_minutes -= self._interval_overlap_minutes(entrada_atual, registro.timestamp, turno)
                total += max(worked_minutes, Decimal("0"))
                entrada_atual = None
        return total

    def _interval_overlap_minutes(self, start: datetime, end: datetime, turno: TurnoHorario) -> Decimal:
        total = Decimal("0")
        for intervalo in turno.intervalos:
            interval_start = datetime.combine(start.date(), intervalo.hora_inicio, tzinfo=start.tzinfo)
            interval_end = datetime.combine(start.date(), intervalo.hora_fim, tzinfo=start.tzinfo)
            overlap_start = max(start, interval_start)
            overlap_end = min(end, interval_end)
            if overlap_end > overlap_start:
                total += Decimal(str((overlap_end - overlap_start).total_seconds() / 60))
        return total

    def _is_date_covered_by_ferias(self, target: date, items: list[Ferias]) -> bool:
        for item in items:
            if item.data_inicio.date() <= target <= item.data_fim.date():
                return True
        return False

    def _group_by_funcionario(self, items):
        grouped = defaultdict(list)
        for item in items:
            grouped[item.funcionario_id].append(item)
        return grouped

    def _competencia_bounds(self, mes: int, ano: int) -> tuple[datetime, datetime]:
        last_day = monthrange(ano, mes)[1]
        return (
            datetime(ano, mes, 1, 0, 0, tzinfo=timezone.utc),
            datetime(ano, mes, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc),
        )

    def _data_agendada_fechamento(self, mes: int, ano: int) -> datetime:
        last_day = monthrange(ano, mes)[1]
        return datetime(ano, mes, last_day, 12, 0, tzinfo=timezone.utc)

    def _validate_competencia(self, mes: int, ano: int) -> None:
        if mes < 1 or mes > 12:
            raise DomainError("Mes de referencia invalido")
        if ano <= 0:
            raise DomainError("Ano de referencia invalido")

    def _ensure_rh_admin(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")

    def _ensure_funcionario(self, current_user: User) -> None:
        if current_user.role != Roles.FUNCIONARIO:
            raise DomainError("Acesso restrito a funcionarios")

    async def _record_audit(
        self,
        current_user: User,
        entity_id: UUID,
        entity_type: str,
        action: str,
        before=None,
        after=None,
        reason: str | None = None,
    ) -> None:
        await self.audit_repo.save(
            RhAuditLog(
                team_id=current_user.team.id,
                actor_user_id=current_user.id,
                actor_role=current_user.role.value,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                before=before,
                after=after,
                reason=reason,
            )
        )

    def _holerite_snapshot(self, holerite: Holerite) -> dict:
        return {
            "funcionario_id": str(holerite.funcionario_id),
            "mes_referencia": holerite.mes_referencia,
            "ano_referencia": holerite.ano_referencia,
            "salario_base": str(holerite.salario_base.amount),
            "horas_extras": str(holerite.horas_extras.amount),
            "descontos_falta": str(holerite.descontos_falta.amount),
            "acrescimos_manuais": str(holerite.acrescimos_manuais.amount),
            "descontos_manuais": str(holerite.descontos_manuais.amount),
            "calculation_hash": holerite.calculation_hash,
            "calculation_version": holerite.calculation_version,
            "valor_liquido": str(holerite.valor_liquido.amount),
            "status": holerite.status.value,
            "pagamento_agendado_id": str(holerite.pagamento_agendado_id) if holerite.pagamento_agendado_id else None,
        }

    def _folha_job_snapshot(self, job: RhFolhaJob) -> dict:
        return {
            "mes": job.mes,
            "ano": job.ano,
            "status": job.status.value,
            "total_funcionarios": job.total_funcionarios,
            "processados": job.processados,
            "falhas": job.falhas,
            "funcionario_ids": [str(item) for item in job.funcionario_ids] if job.funcionario_ids else None,
            "error_summary": job.error_summary,
        }

    def _build_system_user(self, team_id: UUID, requested_by_user_id: UUID | None) -> User:
        team = type("TeamRef", (), {"id": team_id})()
        user = object.__new__(User)
        user.id = requested_by_user_id or UUID("00000000-0000-0000-0000-000000000001")
        user.nome = "Payroll Worker"
        user.email = "worker@engify.local"
        user.senha_hash = ""
        user.role = Roles.ADMIN
        user.team = team
        user.cpf = None
        return user

    def _build_calculation_hash(self, holerite: Holerite, regras, itens: list[HoleriteItem]) -> str:
        payload = {
            "holerite": {
                "funcionario_id": str(holerite.funcionario_id),
                "mes": holerite.mes_referencia,
                "ano": holerite.ano_referencia,
                "salario_base": str(holerite.salario_base.amount),
                "horas_extras": str(holerite.horas_extras.amount),
                "descontos_falta": str(holerite.descontos_falta.amount),
                "acrescimos_manuais": str(holerite.acrescimos_manuais.amount),
                "descontos_manuais": str(holerite.descontos_manuais.amount),
            },
            "regras": [
                {
                    "id": str(regra.id),
                    "codigo": regra.codigo,
                    "prioridade": regra.prioridade,
                    "vigencia_inicio": regra.vigencia_inicio.isoformat() if regra.vigencia_inicio else None,
                    "vigencia_fim": regra.vigencia_fim.isoformat() if regra.vigencia_fim else None,
                    "status": regra.status.value if regra.status == StatusRegraEncargo.ATIVA else regra.status.value,
                }
                for regra in sorted(regras, key=lambda item: (item.prioridade, item.codigo))
            ],
            "itens": [
                {
                    "codigo": item.codigo,
                    "natureza": item.natureza.value,
                    "valor": str(item.valor.amount),
                    "base": str(item.base.amount),
                }
                for item in itens
            ],
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
