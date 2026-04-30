from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.application.providers.repo.rh_repo import (
    BeneficioRepository,
    RegraEncargoRepository,
    RhAuditLogRepository,
    TabelaProgressivaRepository,
)
from app.application.providers.uow import UOWProvider
from app.application.providers.utility.rh_encargo_cache import RhEncargoCachePort
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    BaseCalculoEncargo,
    Beneficio,
    EscopoAplicabilidade,
    FaixaEncargo,
    NaturezaEncargo,
    RegraEncargo,
    RegraEncargoAplicabilidade,
    RhAuditLog,
    StatusBeneficio,
    StatusRegraEncargo,
    TabelaProgressiva,
    TipoRegraEncargo,
)
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError


class RhEncargoService:
    def __init__(
        self,
        regra_repo: RegraEncargoRepository,
        tabela_repo: TabelaProgressivaRepository,
        audit_repo: RhAuditLogRepository,
        uow: UOWProvider,
        encargo_cache: RhEncargoCachePort | None = None,
        beneficio_repo: BeneficioRepository | None = None,
    ) -> None:
        self.regra_repo = regra_repo
        self.tabela_repo = tabela_repo
        self.beneficio_repo = beneficio_repo
        self.audit_repo = audit_repo
        self.uow = uow
        self.encargo_cache = encargo_cache

    async def listar_regras(self, current_user: User, page: int, limit: int, **filters):
        self._ensure_rh_admin(current_user)
        if hasattr(self.regra_repo, "list_by_filters"):
            items = await self.regra_repo.list_by_filters(current_user.team.id, page, limit, **filters)
            total = await self.regra_repo.count_by_filters(current_user.team.id, **filters)
            return items, total
        items = await self.regra_repo.list_by_team(current_user.team.id, page, limit)
        return items, len(items)

    async def obter_regra(self, current_user: User, regra_id: UUID) -> RegraEncargo:
        self._ensure_rh_admin(current_user)
        return await self.regra_repo.get_by_id(regra_id, current_user.team.id)

    async def criar_regra(self, current_user: User, payload) -> RegraEncargo:
        self._ensure_rh_admin(current_user)
        data = self._payload_dict(payload)
        aplicabilidades = self._build_aplicabilidades(current_user.team.id, data.get("aplicabilidades"))
        regra = RegraEncargo(
            team_id=current_user.team.id,
            codigo=data["codigo"],
            nome=data["nome"],
            descricao=data.get("descricao"),
            tipo_calculo=self._enum(TipoRegraEncargo, data["tipo_calculo"]),
            natureza=self._enum(NaturezaEncargo, data["natureza"]),
            base_calculo=self._enum(BaseCalculoEncargo, data["base_calculo"]),
            prioridade=data["prioridade"],
            status=StatusRegraEncargo.RASCUNHO,
            vigencia_inicio=data.get("vigencia_inicio"),
            vigencia_fim=data.get("vigencia_fim"),
            valor_fixo=self._money_or_none(data.get("valor_fixo")),
            percentual=self._decimal_or_none(data.get("percentual")),
            tabela_progressiva_id=data.get("tabela_progressiva_id"),
            teto=self._money_or_none(data.get("teto")),
            piso=self._money_or_none(data.get("piso")),
            arredondamento=data.get("arredondamento", "ROUND_HALF_UP"),
            incide_no_liquido=data.get("incide_no_liquido", True),
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id,
            aplicabilidades=aplicabilidades,
        )
        saved = await self.regra_repo.save(regra)
        await self._record_audit(current_user, "regra_encargo", saved.id, "rh.regra_encargo.created", after=self._regra_snapshot(saved))
        await self.uow.commit()
        return saved

    async def atualizar_regra(self, current_user: User, regra_id: UUID, payload) -> RegraEncargo:
        self._ensure_rh_admin(current_user)
        regra = await self.regra_repo.get_by_id(regra_id, current_user.team.id)
        if regra.status != StatusRegraEncargo.RASCUNHO:
            raise DomainError("Somente regra em rascunho pode ser atualizada")
        before = self._regra_snapshot(regra)
        self._apply_regra_updates(regra, self._payload_dict(payload), current_user)
        self._validate_regra(regra)
        saved = await self.regra_repo.save(regra)
        await self._record_audit(current_user, "regra_encargo", saved.id, "rh.regra_encargo.updated_draft", before=before, after=self._regra_snapshot(saved))
        await self.uow.commit()
        return saved

    async def criar_nova_versao(self, current_user: User, regra_id: UUID, payload=None) -> RegraEncargo:
        self._ensure_rh_admin(current_user)
        original = await self.regra_repo.get_by_id(regra_id, current_user.team.id)
        data = self._payload_dict(payload or {})
        nova = RegraEncargo(
            team_id=current_user.team.id,
            codigo=data.get("codigo", original.codigo),
            nome=data.get("nome", original.nome),
            descricao=data.get("descricao", original.descricao),
            tipo_calculo=self._enum(TipoRegraEncargo, data.get("tipo_calculo", original.tipo_calculo)),
            natureza=self._enum(NaturezaEncargo, data.get("natureza", original.natureza)),
            base_calculo=self._enum(BaseCalculoEncargo, data.get("base_calculo", original.base_calculo)),
            prioridade=data.get("prioridade", original.prioridade),
            status=StatusRegraEncargo.RASCUNHO,
            vigencia_inicio=data.get("vigencia_inicio", original.vigencia_inicio),
            vigencia_fim=data.get("vigencia_fim", original.vigencia_fim),
            valor_fixo=self._money_or_none(data.get("valor_fixo", original.valor_fixo)),
            percentual=self._decimal_or_none(data.get("percentual", original.percentual)),
            tabela_progressiva_id=data.get("tabela_progressiva_id", original.tabela_progressiva_id),
            teto=self._money_or_none(data.get("teto", original.teto)),
            piso=self._money_or_none(data.get("piso", original.piso)),
            arredondamento=data.get("arredondamento", original.arredondamento),
            incide_no_liquido=data.get("incide_no_liquido", original.incide_no_liquido),
            regra_grupo_id=original.regra_grupo_id,
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id,
            aplicabilidades=self._clone_aplicabilidades(current_user.team.id, data.get("aplicabilidades", original.aplicabilidades)),
        )
        saved = await self.regra_repo.save(nova)
        await self._record_audit(current_user, "regra_encargo", saved.id, "rh.regra_encargo.version_created", after=self._regra_snapshot(saved))
        await self._invalidate_cache(current_user.team.id)
        await self.uow.commit()
        return saved

    async def ativar_regra(self, current_user: User, regra_id: UUID, motivo: str) -> RegraEncargo:
        self._ensure_rh_admin(current_user)
        self._ensure_motivo(motivo, "Motivo para ativar regra e obrigatorio")
        regra = await self.regra_repo.get_by_id(regra_id, current_user.team.id)
        if regra.status == StatusRegraEncargo.ARQUIVADA:
            raise DomainError("Regra arquivada nao pode ser ativada")
        if regra.vigencia_inicio is None:
            raise DomainError("Regra ativa exige vigencia inicial")
        if await self._has_regra_conflict(regra):
            raise DomainError("Existe conflito de vigencia para esta regra e aplicabilidade")
        before = self._regra_snapshot(regra)
        regra.status = StatusRegraEncargo.ATIVA
        self._validate_regra(regra)
        regra.approved_by_user_id = current_user.id
        regra.updated_by_user_id = current_user.id
        saved = await self.regra_repo.save(regra)
        await self._record_audit(current_user, "regra_encargo", saved.id, "rh.regra_encargo.activated", before=before, after=self._regra_snapshot(saved), reason=motivo)
        await self._invalidate_cache(current_user.team.id)
        await self.uow.commit()
        return saved

    async def inativar_regra(self, current_user: User, regra_id: UUID, motivo: str) -> RegraEncargo:
        self._ensure_rh_admin(current_user)
        self._ensure_motivo(motivo, "Motivo para inativar regra e obrigatorio")
        regra = await self.regra_repo.get_by_id(regra_id, current_user.team.id)
        if regra.status == StatusRegraEncargo.ARQUIVADA:
            raise DomainError("Regra arquivada nao pode ser inativada")
        before = self._regra_snapshot(regra)
        regra.status = StatusRegraEncargo.INATIVA
        regra.updated_by_user_id = current_user.id
        saved = await self.regra_repo.save(regra)
        await self._record_audit(current_user, "regra_encargo", saved.id, "rh.regra_encargo.inactivated", before=before, after=self._regra_snapshot(saved), reason=motivo)
        await self._invalidate_cache(current_user.team.id)
        await self.uow.commit()
        return saved

    async def arquivar_regra(self, current_user: User, regra_id: UUID) -> RegraEncargo:
        self._ensure_rh_admin(current_user)
        regra = await self.regra_repo.get_by_id(regra_id, current_user.team.id)
        if regra.status == StatusRegraEncargo.ATIVA:
            raise DomainError("Regra ativa deve ser inativada antes de arquivar")
        before = self._regra_snapshot(regra)
        regra.status = StatusRegraEncargo.ARQUIVADA
        regra.is_deleted = True
        saved = await self.regra_repo.save(regra)
        await self._record_audit(current_user, "regra_encargo", saved.id, "rh.regra_encargo.archived", before=before, after=self._regra_snapshot(saved))
        await self._invalidate_cache(current_user.team.id)
        await self.uow.commit()
        return saved

    async def listar_tabelas_progressivas(self, current_user: User, page: int, limit: int, **filters):
        self._ensure_rh_admin(current_user)
        if hasattr(self.tabela_repo, "list_by_filters"):
            items = await self.tabela_repo.list_by_filters(current_user.team.id, page, limit, **filters)
            total = await self.tabela_repo.count_by_filters(current_user.team.id, **filters)
            return items, total
        items = await self.tabela_repo.list_by_team(current_user.team.id, page, limit)
        return items, len(items)

    async def listar_beneficios(self, current_user: User, page: int, limit: int, **filters):
        self._ensure_rh_read(current_user)
        repo = self._ensure_beneficio_repo()
        items = await repo.list_by_filters(current_user.team.id, page, limit, **filters)
        total = await repo.count_by_filters(current_user.team.id, **filters)
        return items, total

    async def criar_beneficio(self, current_user: User, payload) -> Beneficio:
        self._ensure_rh_admin(current_user)
        repo = self._ensure_beneficio_repo()
        data = self._payload_dict(payload)
        await self._ensure_beneficio_nome_available(current_user.team.id, data["nome"])
        beneficio = Beneficio(
            team_id=current_user.team.id,
            nome=data["nome"],
            descricao=data.get("descricao"),
            status=StatusBeneficio.ATIVO,
            created_by_user_id=current_user.id,
        )
        saved = await repo.save(beneficio)
        await self._record_audit(current_user, "beneficio", saved.id, "rh.beneficio.created", after=self._beneficio_snapshot(saved))
        await self.uow.commit()
        return saved

    async def atualizar_beneficio(self, current_user: User, beneficio_id: UUID, payload) -> Beneficio:
        self._ensure_rh_admin(current_user)
        repo = self._ensure_beneficio_repo()
        beneficio = await repo.get_by_id(beneficio_id, current_user.team.id)
        before = self._beneficio_snapshot(beneficio)
        data = self._payload_dict(payload)
        novo_nome = data.get("nome")
        if novo_nome is not None and novo_nome.strip().lower() != beneficio.nome.strip().lower():
            await self._ensure_beneficio_nome_available(current_user.team.id, novo_nome)
        beneficio.atualizar(nome=novo_nome, descricao=data.get("descricao"))
        saved = await repo.save(beneficio)
        await self._record_audit(current_user, "beneficio", saved.id, "rh.beneficio.updated", before=before, after=self._beneficio_snapshot(saved))
        await self.uow.commit()
        return saved

    async def inativar_beneficio(self, current_user: User, beneficio_id: UUID, motivo: str) -> Beneficio:
        self._ensure_rh_admin(current_user)
        self._ensure_motivo(motivo, "Motivo para inativar beneficio e obrigatorio")
        repo = self._ensure_beneficio_repo()
        beneficio = await repo.get_by_id(beneficio_id, current_user.team.id)
        before = self._beneficio_snapshot(beneficio)
        beneficio.inativar()
        saved = await repo.save(beneficio)
        await self._record_audit(current_user, "beneficio", saved.id, "rh.beneficio.inactivated", before=before, after=self._beneficio_snapshot(saved), reason=motivo)
        await self.uow.commit()
        return saved

    async def reativar_beneficio(self, current_user: User, beneficio_id: UUID, motivo: str) -> Beneficio:
        self._ensure_rh_admin(current_user)
        self._ensure_motivo(motivo, "Motivo para reativar beneficio e obrigatorio")
        repo = self._ensure_beneficio_repo()
        beneficio = await repo.get_by_id(beneficio_id, current_user.team.id)
        existing = await repo.get_active_by_nome(current_user.team.id, beneficio.nome)
        if existing is not None and existing.id != beneficio.id:
            raise DomainError("Ja existe um beneficio ativo com este nome")
        before = self._beneficio_snapshot(beneficio)
        beneficio.reativar()
        saved = await repo.save(beneficio)
        await self._record_audit(current_user, "beneficio", saved.id, "rh.beneficio.reactivated", before=before, after=self._beneficio_snapshot(saved), reason=motivo)
        await self.uow.commit()
        return saved

    async def obter_tabela_progressiva(self, current_user: User, tabela_id: UUID) -> TabelaProgressiva:
        self._ensure_rh_admin(current_user)
        return await self.tabela_repo.get_by_id(tabela_id, current_user.team.id)

    async def criar_tabela_progressiva(self, current_user: User, payload) -> TabelaProgressiva:
        self._ensure_rh_admin(current_user)
        data = self._payload_dict(payload)
        tabela = TabelaProgressiva(
            team_id=current_user.team.id,
            codigo=data["codigo"],
            nome=data["nome"],
            descricao=data.get("descricao"),
            vigencia_inicio=data.get("vigencia_inicio"),
            vigencia_fim=data.get("vigencia_fim"),
            status=StatusRegraEncargo.RASCUNHO,
            created_by_user_id=current_user.id,
        )
        saved = await self.tabela_repo.save(tabela)
        await self._record_audit(current_user, "tabela_progressiva", saved.id, "rh.tabela_progressiva.created", after=self._tabela_snapshot(saved))
        await self.uow.commit()
        return saved

    async def atualizar_tabela_progressiva(self, current_user: User, tabela_id: UUID, payload) -> TabelaProgressiva:
        self._ensure_rh_admin(current_user)
        tabela = await self.tabela_repo.get_by_id(tabela_id, current_user.team.id)
        self._ensure_tabela_editavel(tabela)
        before = self._tabela_snapshot(tabela)
        data = self._payload_dict(payload)
        for attr in ("codigo", "nome", "descricao", "vigencia_inicio", "vigencia_fim"):
            if attr in data:
                setattr(tabela, attr, data[attr])
        self._validate_vigencia(tabela.vigencia_inicio, tabela.vigencia_fim)
        saved = await self.tabela_repo.save(tabela)
        await self._record_audit(current_user, "tabela_progressiva", saved.id, "rh.tabela_progressiva.updated_draft", before=before, after=self._tabela_snapshot(saved))
        await self.uow.commit()
        return saved

    async def substituir_faixas_tabela(self, current_user: User, tabela_id: UUID, faixas_payload) -> TabelaProgressiva:
        self._ensure_rh_admin(current_user)
        tabela = await self.tabela_repo.get_by_id(tabela_id, current_user.team.id)
        self._ensure_tabela_editavel(tabela)
        before = self._tabela_snapshot(tabela)
        tabela.faixas = self._build_faixas(current_user.team.id, faixas_payload)
        self._validate_faixas(tabela.faixas, allow_empty=True)
        saved = await self.tabela_repo.save(tabela)
        await self._record_audit(current_user, "tabela_progressiva", saved.id, "rh.tabela_progressiva.updated_draft", before=before, after=self._tabela_snapshot(saved))
        await self.uow.commit()
        return saved

    async def ativar_tabela_progressiva(self, current_user: User, tabela_id: UUID, motivo: str) -> TabelaProgressiva:
        self._ensure_rh_admin(current_user)
        self._ensure_motivo(motivo, "Motivo para ativar tabela progressiva e obrigatorio")
        tabela = await self.tabela_repo.get_by_id(tabela_id, current_user.team.id)
        if tabela.vigencia_inicio is None:
            raise DomainError("Tabela progressiva ativa exige vigencia inicial")
        self._validate_faixas(tabela.faixas, allow_empty=False)
        before = self._tabela_snapshot(tabela)
        tabela.status = StatusRegraEncargo.ATIVA
        tabela.approved_by_user_id = current_user.id
        saved = await self.tabela_repo.save(tabela)
        await self._record_audit(current_user, "tabela_progressiva", saved.id, "rh.tabela_progressiva.activated", before=before, after=self._tabela_snapshot(saved), reason=motivo)
        await self._invalidate_cache(current_user.team.id)
        await self.uow.commit()
        return saved

    async def inativar_tabela_progressiva(self, current_user: User, tabela_id: UUID, motivo: str) -> TabelaProgressiva:
        self._ensure_rh_admin(current_user)
        self._ensure_motivo(motivo, "Motivo para inativar tabela progressiva e obrigatorio")
        tabela = await self.tabela_repo.get_by_id(tabela_id, current_user.team.id)
        before = self._tabela_snapshot(tabela)
        tabela.status = StatusRegraEncargo.INATIVA
        saved = await self.tabela_repo.save(tabela)
        await self._record_audit(current_user, "tabela_progressiva", saved.id, "rh.tabela_progressiva.inactivated", before=before, after=self._tabela_snapshot(saved), reason=motivo)
        await self._invalidate_cache(current_user.team.id)
        await self.uow.commit()
        return saved

    def _ensure_rh_admin(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")

    def _ensure_rh_read(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")

    def _ensure_beneficio_repo(self) -> BeneficioRepository:
        if self.beneficio_repo is None:
            raise DomainError("Recurso de beneficios indisponivel")
        return self.beneficio_repo

    async def _ensure_beneficio_nome_available(self, team_id: UUID, nome: str) -> None:
        existing = await self._ensure_beneficio_repo().get_active_by_nome(team_id, nome)
        if existing is not None:
            raise DomainError("Ja existe um beneficio ativo com este nome")

    def _ensure_tabela_editavel(self, tabela: TabelaProgressiva) -> None:
        if tabela.status == StatusRegraEncargo.ATIVA:
            raise DomainError("Tabela progressiva ativa nao pode ser editada diretamente")

    async def _has_regra_conflict(self, regra: RegraEncargo) -> bool:
        if hasattr(self.regra_repo, "has_active_conflict"):
            return await self.regra_repo.has_active_conflict(
                regra.team_id,
                regra.regra_grupo_id,
                regra.codigo,
                regra.vigencia_inicio,
                regra.vigencia_fim,
                regra.aplicabilidades,
                exclude_id=regra.id,
            )
        regras, _ = await self.listar_regras(self._system_user(regra.team_id), 1, 10_000)
        for item in regras:
            if item.id == regra.id or item.status != StatusRegraEncargo.ATIVA:
                continue
            if item.codigo == regra.codigo and item.regra_grupo_id == regra.regra_grupo_id and self._vigencias_sobrepoem(regra, item):
                if {(a.escopo, a.valor) for a in item.aplicabilidades} == {(a.escopo, a.valor) for a in regra.aplicabilidades}:
                    return True
        return False

    def _apply_regra_updates(self, regra: RegraEncargo, data: dict, current_user: User) -> None:
        enum_fields = {
            "tipo_calculo": TipoRegraEncargo,
            "natureza": NaturezaEncargo,
            "base_calculo": BaseCalculoEncargo,
        }
        money_fields = {"valor_fixo", "teto", "piso"}
        for attr, value in data.items():
            if attr == "aplicabilidades":
                regra.aplicabilidades = self._build_aplicabilidades(current_user.team.id, value)
            elif attr in enum_fields:
                setattr(regra, attr, self._enum(enum_fields[attr], value))
            elif attr in money_fields:
                setattr(regra, attr, self._money_or_none(value))
            elif attr == "percentual":
                regra.percentual = self._decimal_or_none(value)
            elif attr != "status":
                setattr(regra, attr, value)
        regra.updated_by_user_id = current_user.id

    def _build_aplicabilidades(self, team_id: UUID, items) -> list[RegraEncargoAplicabilidade]:
        if not items:
            return [RegraEncargoAplicabilidade(team_id=team_id, escopo=EscopoAplicabilidade.TODOS_FUNCIONARIOS)]
        return self._clone_aplicabilidades(team_id, items)

    def _clone_aplicabilidades(self, team_id: UUID, items) -> list[RegraEncargoAplicabilidade]:
        cloned = []
        for item in items:
            data = self._payload_dict(item)
            escopo = self._enum(EscopoAplicabilidade, data["escopo"])
            cloned.append(RegraEncargoAplicabilidade(team_id=team_id, escopo=escopo, valor=data.get("valor")))
        return cloned

    def _build_faixas(self, team_id: UUID, items) -> list[FaixaEncargo]:
        faixas = []
        for item in items or []:
            data = self._payload_dict(item)
            faixas.append(
                FaixaEncargo(
                    team_id=team_id,
                    ordem=data["ordem"],
                    valor_inicial=Money(self._decimal(data["valor_inicial"])),
                    valor_final=Money(self._decimal(data["valor_final"])) if data.get("valor_final") is not None else None,
                    aliquota=self._decimal(data["aliquota"]),
                    deducao=Money(self._decimal(data.get("deducao", Decimal("0.00")))),
                    calculo_marginal=data.get("calculo_marginal", False),
                )
            )
        return faixas

    def _validate_faixas(self, faixas: list[FaixaEncargo], allow_empty: bool) -> None:
        if not faixas:
            if allow_empty:
                return
            raise DomainError("Tabela progressiva ativa exige ao menos uma faixa valida")
        ordered = sorted(faixas, key=lambda item: item.ordem)
        if [item.ordem for item in ordered] != sorted({item.ordem for item in ordered}):
            raise DomainError("Faixas progressivas devem ter ordem unica")
        previous_end = None
        for faixa in ordered:
            start = faixa.valor_inicial.amount
            end = faixa.valor_final.amount if faixa.valor_final is not None else None
            if end is not None and end < start:
                raise DomainError("Limites da faixa sao incoerentes")
            if previous_end is not None and start < previous_end:
                raise DomainError("Faixas progressivas nao podem se sobrepor")
            previous_end = end if end is not None else previous_end

    def _validate_vigencia(self, start, end) -> None:
        if start and end and end < start:
            raise DomainError("Vigencia final nao pode ser anterior a vigencia inicial")

    def _validate_regra(self, regra: RegraEncargo) -> None:
        self._validate_vigencia(regra.vigencia_inicio, regra.vigencia_fim)
        if regra.prioridade < 0:
            raise DomainError("Prioridade da regra nao pode ser negativa")
        if regra.percentual is not None and Decimal(str(regra.percentual)) > Decimal("100.00"):
            raise DomainError("Percentual da regra deve estar entre 0 e 100")

    async def _record_audit(self, current_user: User, entity_type: str, entity_id: UUID, action: str, before=None, after=None, reason: str | None = None) -> None:
        await self.audit_repo.save(
            RhAuditLog(
                team_id=current_user.team.id,
                actor_user_id=current_user.id,
                actor_role=current_user.role.value,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                before=self._mask_sensitive(before),
                after=self._mask_sensitive(after),
                reason=reason,
            )
        )

    async def _invalidate_cache(self, team_id: UUID) -> None:
        if self.encargo_cache is not None:
            await self.encargo_cache.invalidate_team(team_id)

    def _regra_snapshot(self, regra: RegraEncargo) -> dict:
        return {
            "codigo": regra.codigo,
            "nome": regra.nome,
            "tipo_calculo": regra.tipo_calculo.value,
            "natureza": regra.natureza.value,
            "base_calculo": regra.base_calculo.value,
            "status": regra.status.value,
            "vigencia_inicio": regra.vigencia_inicio.isoformat() if regra.vigencia_inicio else None,
            "vigencia_fim": regra.vigencia_fim.isoformat() if regra.vigencia_fim else None,
            "valor_fixo": str(regra.valor_fixo.amount) if regra.valor_fixo else None,
            "percentual": str(regra.percentual) if regra.percentual is not None else None,
            "tabela_progressiva_id": str(regra.tabela_progressiva_id) if regra.tabela_progressiva_id else None,
            "aplicabilidades": [{"escopo": item.escopo.value, "valor": item.valor} for item in regra.aplicabilidades],
        }

    def _tabela_snapshot(self, tabela: TabelaProgressiva) -> dict:
        return {
            "codigo": tabela.codigo,
            "nome": tabela.nome,
            "status": tabela.status.value,
            "vigencia_inicio": tabela.vigencia_inicio.isoformat() if tabela.vigencia_inicio else None,
            "vigencia_fim": tabela.vigencia_fim.isoformat() if tabela.vigencia_fim else None,
            "faixas": [
                {
                    "ordem": faixa.ordem,
                    "valor_inicial": str(faixa.valor_inicial.amount),
                    "valor_final": str(faixa.valor_final.amount) if faixa.valor_final else None,
                    "aliquota": str(faixa.aliquota),
                }
                for faixa in tabela.faixas
            ],
        }

    def _beneficio_snapshot(self, beneficio: Beneficio) -> dict:
        return {
            "nome": beneficio.nome,
            "descricao": beneficio.descricao,
            "status": beneficio.status.value,
            "is_deleted": beneficio.is_deleted,
        }

    def _mask_sensitive(self, payload):
        if payload is None:
            return None
        masked = deepcopy(payload)
        for key in list(masked.keys()) if isinstance(masked, dict) else []:
            if "salario" in key.lower() or "cpf" in key.lower() or "snapshot" in key.lower():
                masked[key] = "***"
        return masked

    def _payload_dict(self, payload) -> dict:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return dict(payload)
        if hasattr(payload, "model_dump"):
            return payload.model_dump(exclude_unset=True)
        return dict(payload.__dict__)

    def _enum(self, enum_cls, value):
        return value if isinstance(value, enum_cls) else enum_cls(value)

    def _money_or_none(self, value) -> Money | None:
        if value is None:
            return None
        if isinstance(value, Money):
            return value
        return Money(self._decimal(value))

    def _decimal_or_none(self, value) -> Decimal | None:
        if value is None:
            return None
        return self._decimal(value)

    def _decimal(self, value) -> Decimal:
        return value if isinstance(value, Decimal) else Decimal(str(value))

    def _ensure_motivo(self, motivo: str, message: str) -> None:
        if not motivo or not motivo.strip():
            raise DomainError(message)

    def _vigencias_sobrepoem(self, a: RegraEncargo, b: RegraEncargo) -> bool:
        open_end = datetime.max.replace(tzinfo=timezone.utc)
        return a.vigencia_inicio <= (b.vigencia_fim or open_end) and (a.vigencia_fim or open_end) >= b.vigencia_inicio

    def _system_user(self, team_id: UUID) -> User:
        team = type("TeamRef", (), {"id": team_id})()
        user = object.__new__(User)
        user.id = UUID("00000000-0000-0000-0000-000000000001")
        user.role = Roles.ADMIN
        user.team = team
        return user
