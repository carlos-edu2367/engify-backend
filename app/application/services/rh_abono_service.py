from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from uuid import UUID

from app.application.dtos.rh import AbonarFaltasDTO, RhFaltaPendenteDTO
from app.application.providers.repo.rh_repo import (
    AbonoFaltaRepository,
    AtestadoRepository,
    EventoCalendarioRepository,
    FeriasRepository,
    FuncionarioRepository,
    HorarioTrabalhoRepository,
    RegistroPontoRepository,
    TipoAtestadoRepository,
)
from app.application.providers.uow import UOWProvider
from app.core.tempo import day_bounds, local_tz
from app.domain.entities.rh import Atestado, Funcionario, RhAuditLog, StatusAtestado, StatusFerias
from app.domain.entities.rh_abono import AbonoFalta
from app.domain.entities.rh_calendario import TipoEventoCalendario
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError
from app.domain.services.rh_ponto_calculo import SituacaoDia, resumir_periodo

_EVENTOS_QUE_ABONAM = {
    TipoEventoCalendario.FERIADO,
    TipoEventoCalendario.PONTO_FACULTATIVO,
    TipoEventoCalendario.ABONO,
}


class RhAbonoService:
    def __init__(
        self,
        funcionario_repo: FuncionarioRepository,
        horario_repo: HorarioTrabalhoRepository,
        registro_ponto_repo: RegistroPontoRepository,
        ferias_repo: FeriasRepository,
        atestado_repo: AtestadoRepository,
        tipo_atestado_repo: TipoAtestadoRepository,
        abono_repo: AbonoFaltaRepository,
        audit_repo,
        uow: UOWProvider,
        evento_calendario_repo: EventoCalendarioRepository | None = None,
    ) -> None:
        self.funcionario_repo = funcionario_repo
        self.horario_repo = horario_repo
        self.registro_ponto_repo = registro_ponto_repo
        self.ferias_repo = ferias_repo
        self.atestado_repo = atestado_repo
        self.tipo_atestado_repo = tipo_atestado_repo
        self.abono_repo = abono_repo
        self.audit_repo = audit_repo
        self.uow = uow
        self.evento_calendario_repo = evento_calendario_repo

    async def listar_faltas(
        self,
        current_user: User,
        start: date,
        end: date,
        funcionario_id: UUID | None = None,
    ) -> list[RhFaltaPendenteDTO]:
        self._ensure_rh_admin(current_user)
        team_id = current_user.team.id
        funcionarios = await self._load_funcionarios(team_id, funcionario_id)
        if not funcionarios:
            return []

        funcionario_ids = [item.id for item in funcionarios]
        horarios = await self.horario_repo.list_by_funcionarios(team_id, funcionario_ids)
        start_dt, end_dt = day_bounds(start)[0], day_bounds(end)[1]

        registros = await self.registro_ponto_repo.list_by_competencia(team_id, funcionario_ids, start_dt, end_dt)
        ferias_items = await self.ferias_repo.list_by_competencia(
            team_id, funcionario_ids, start_dt, end_dt, statuses={StatusFerias.APROVADO, StatusFerias.EM_ANDAMENTO}
        )
        atestados = await self.atestado_repo.list_by_competencia(
            team_id, funcionario_ids, start_dt, end_dt, statuses={StatusAtestado.ENTREGUE}
        )
        abono_por_atestado = await self._build_atestado_abono_map(team_id, atestados)
        abonos_existentes = await self.abono_repo.list_by_periodo(team_id, start, end)
        eventos = (
            await self.evento_calendario_repo.list_by_periodo(team_id, start, end)
            if self.evento_calendario_repo is not None
            else []
        )

        registros_por_funcionario = self._group_by_funcionario(registros)
        ferias_por_funcionario = self._group_by_funcionario(ferias_items)
        abonos_por_funcionario: dict[UUID, set[date]] = defaultdict(set)
        for abono in abonos_existentes:
            abonos_por_funcionario[abono.funcionario_id].add(abono.data)

        pendentes: list[RhFaltaPendenteDTO] = []
        for funcionario in funcionarios:
            horario = horarios.get(funcionario.id)
            if horario is None:
                continue

            datas_abonadas = set(abono_por_atestado.get(funcionario.id, set()))
            datas_abonadas |= abonos_por_funcionario.get(funcionario.id, set())
            for ferias in ferias_por_funcionario.get(funcionario.id, []):
                dia = ferias.data_inicio.date()
                fim_ferias = ferias.data_fim.date()
                while dia <= fim_ferias:
                    datas_abonadas.add(dia)
                    dia += timedelta(days=1)
            for evento in eventos:
                if evento.tipo in _EVENTOS_QUE_ABONAM and evento.aplica_a(funcionario.id):
                    datas_abonadas.add(evento.data)

            resumo = resumir_periodo(
                registros=registros_por_funcionario.get(funcionario.id, []),
                turno_para_dia=horario.turno_para_dia,
                inicio=start,
                fim=end,
                datas_abonadas=datas_abonadas,
                tz=local_tz(),
            )
            for dia in resumo.dias:
                if dia.situacao == SituacaoDia.FALTA:
                    pendentes.append(
                        RhFaltaPendenteDTO(funcionario_id=funcionario.id, funcionario_nome=funcionario.nome, data=dia.data)
                    )

        pendentes.sort(key=lambda item: (item.data, item.funcionario_nome))
        return pendentes

    async def abonar(self, dto: AbonarFaltasDTO, current_user: User) -> list[AbonoFalta]:
        self._ensure_rh_admin(current_user)
        team_id = current_user.team.id

        datas = [item.data for item in dto.itens]
        existentes = await self.abono_repo.list_by_periodo(team_id, min(datas), max(datas))
        ja_abonadas = {(item.funcionario_id, item.data) for item in existentes}

        criados: list[AbonoFalta] = []
        vistos: set[tuple[UUID, date]] = set()
        for item in dto.itens:
            chave = (item.funcionario_id, item.data)
            if chave in ja_abonadas or chave in vistos:
                continue
            vistos.add(chave)
            abono = AbonoFalta(
                team_id=team_id,
                funcionario_id=item.funcionario_id,
                data=item.data,
                motivo=dto.motivo,
                created_by_user_id=current_user.id,
            )
            saved = await self.abono_repo.save(abono)
            criados.append(saved)
            await self._record_audit(current_user, saved.id, "rh.abono.criado", after=self._snapshot(saved))

        if criados:
            await self.uow.commit()
        return criados

    async def listar_abonos(
        self,
        current_user: User,
        start: date,
        end: date,
        funcionario_id: UUID | None = None,
    ) -> list[AbonoFalta]:
        self._ensure_rh_admin(current_user)
        return await self.abono_repo.list_by_periodo(current_user.team.id, start, end, funcionario_id=funcionario_id)

    async def revogar(self, abono_id: UUID, current_user: User) -> AbonoFalta:
        self._ensure_rh_admin(current_user)
        abono = await self.abono_repo.get_by_id(abono_id, current_user.team.id)
        before = self._snapshot(abono)
        abono.revogar()
        saved = await self.abono_repo.save(abono)
        await self._record_audit(current_user, saved.id, "rh.abono.revogado", before=before)
        await self.uow.commit()
        return saved

    async def listar_meus_abonos(self, current_user: User, desde: date, ate: date) -> list[AbonoFalta]:
        funcionario = await self.funcionario_repo.get_by_user_id(current_user.team.id, current_user.id)
        if funcionario is None:
            return []
        return await self.abono_repo.list_by_funcionario_periodo(current_user.team.id, funcionario.id, desde, ate)

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

    async def _build_atestado_abono_map(self, team_id: UUID, atestados: list[Atestado]) -> dict[UUID, set[date]]:
        grouped: dict[UUID, set[date]] = defaultdict(set)
        tipos_cache: dict[UUID, bool] = {}
        for atestado in atestados:
            if atestado.tipo_atestado_id not in tipos_cache:
                tipo = await self.tipo_atestado_repo.get_by_id(atestado.tipo_atestado_id, team_id)
                tipos_cache[atestado.tipo_atestado_id] = tipo.abona_falta
            if not tipos_cache[atestado.tipo_atestado_id]:
                continue
            dia = atestado.data_inicio.date()
            fim = atestado.data_fim.date()
            while dia <= fim:
                grouped[atestado.funcionario_id].add(dia)
                dia += timedelta(days=1)
        return grouped

    def _group_by_funcionario(self, items):
        grouped: dict[UUID, list] = defaultdict(list)
        for item in items:
            grouped[item.funcionario_id].append(item)
        return grouped

    def _ensure_rh_admin(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")

    def _snapshot(self, abono: AbonoFalta) -> dict:
        return {
            "funcionario_id": str(abono.funcionario_id),
            "data": abono.data.isoformat(),
            "motivo": abono.motivo,
            "is_deleted": abono.is_deleted,
        }

    async def _record_audit(self, current_user: User, entity_id: UUID, action: str, before=None, after=None) -> None:
        await self.audit_repo.save(
            RhAuditLog(
                team_id=current_user.team.id,
                actor_user_id=current_user.id,
                actor_role=current_user.role.value,
                entity_type="abono_falta",
                entity_id=entity_id,
                action=action,
                before=before,
                after=after,
            )
        )
