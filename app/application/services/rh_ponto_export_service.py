"""Exportacao dos registros de ponto no formato de cartao para assinatura."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from app.application.providers.repo.rh_repo import (
    AbonoFaltaRepository,
    FuncionarioRepository,
    HorarioTrabalhoRepository,
    RegistroPontoRepository,
)
from app.application.providers.utility.cartao_ponto_builder import (
    CartaoFuncionario,
    CartaoPontoBuilder,
    DiaCartao,
)
from app.core.tempo import day_bounds, local_date_of, local_tz
from app.domain.entities.rh import HorarioTrabalho, RegistroPonto
from app.domain.entities.rh_abono import separar_abonos
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError
from app.domain.services.rh_cartao_ponto import montar_linha
from app.domain.services.rh_ponto_calculo import resultado_dia, _abater_minutos_abonados

_MAX_DIAS = 366
_MAX_FUNCIONARIOS = 500


class RhPontoExportService:
    def __init__(
        self,
        funcionario_repo: FuncionarioRepository,
        registro_ponto_repo: RegistroPontoRepository,
        builder: CartaoPontoBuilder | None = None,
        horario_repo: HorarioTrabalhoRepository | None = None,
        abono_repo: AbonoFaltaRepository | None = None,
    ) -> None:
        self.funcionario_repo = funcionario_repo
        self.registro_ponto_repo = registro_ponto_repo
        self.builder = builder or CartaoPontoBuilder()
        self.horario_repo = horario_repo
        self.abono_repo = abono_repo

    async def exportar_cartoes(
        self,
        current_user: User,
        inicio: date,
        fim: date,
        funcionario_id: UUID | None = None,
    ) -> bytes:
        self._ensure_rh_admin(current_user)
        self._ensure_periodo_valido(inicio, fim)

        team_id = current_user.team.id
        funcionarios = await self._resolver_funcionarios(team_id, funcionario_id)

        janela_inicio = day_bounds(inicio)[0]
        janela_fim = day_bounds(fim)[1]
        registros = await self.registro_ponto_repo.list_by_competencia(
            team_id,
            [f.id for f in funcionarios],
            janela_inicio,
            janela_fim,
        )

        abonos_por_func = {}
        minutos_abonados_por_func = {}
        if self.abono_repo is not None:
            abonos_existentes = await self.abono_repo.list_by_periodo(team_id, inicio, fim)
            datas_abonadas, minutos_abonados = separar_abonos(abonos_existentes)
            abonos_por_func = datas_abonadas
            minutos_abonados_por_func = minutos_abonados

        tz = local_tz()
        por_funcionario_e_dia: dict[tuple[UUID, date], list[RegistroPonto]] = defaultdict(list)
        for registro in registros:
            chave = (registro.funcionario_id, local_date_of(registro.timestamp))
            por_funcionario_e_dia[chave].append(registro)

        horarios = await self._horarios_por_funcionario(team_id, funcionarios)

        dias_do_periodo = self._dias_do_periodo(inicio, fim)
        cartoes = [
            CartaoFuncionario(
                nome=funcionario.nome,
                cargo=funcionario.cargo,
                dias=[
                    self._montar_dia(
                        dia,
                        por_funcionario_e_dia.get((funcionario.id, dia), []),
                        horarios.get(funcionario.id),
                        tz,
                        datas_abonadas=abonos_por_func.get(funcionario.id, set()),
                        minutos_abonados=minutos_abonados_por_func.get(funcionario.id, {}),
                    )
                    for dia in dias_do_periodo
                ],
            )
            for funcionario in funcionarios
        ]

        return self.builder.build(
            empresa=self._empresa(current_user),
            inicio=inicio,
            fim=fim,
            cartoes=cartoes,
        )

    async def _horarios_por_funcionario(self, team_id: UUID, funcionarios: list) -> dict[UUID, HorarioTrabalho]:
        if self.horario_repo is None:
            return {}
        return await self.horario_repo.list_by_funcionarios(team_id, [f.id for f in funcionarios])

    def _montar_dia(
        self,
        dia: date,
        registros_do_dia: list[RegistroPonto],
        horario: HorarioTrabalho | None,
        tz,
        datas_abonadas: set[date] | None = None,
        minutos_abonados: dict[date, Decimal] | None = None,
    ) -> DiaCartao:
        # Sem horario cadastrado o turno do dia e sempre None; resultado_dia trata isso como
        # esperado=0, entao qualquer batida vira hora extra em vez de sumir do cartao.
        turno = horario.turno_para_dia(dia.weekday()) if horario is not None else None
        datas_abonadas = datas_abonadas or set()
        minutos_abonados = minutos_abonados or {}

        if dia in datas_abonadas:
            resultado = resultado_dia(registros_do_dia, turno, esperado_min_override=Decimal("0"))
        else:
            resultado = resultado_dia(registros_do_dia, turno)
            resultado = _abater_minutos_abonados(resultado, minutos_abonados.get(dia, Decimal("0")))

        return DiaCartao(
            data=dia,
            linha=montar_linha(registros_do_dia, tz),
            extra_min=resultado.extra_min,
            falta_min=resultado.falta_min,
        )

    def nome_arquivo(self, inicio: date, fim: date) -> str:
        return f"cartoes-ponto-{inicio.isoformat()}-a-{fim.isoformat()}.xlsx"

    async def _resolver_funcionarios(self, team_id: UUID, funcionario_id: UUID | None):
        if funcionario_id is not None:
            return [await self.funcionario_repo.get_by_id(funcionario_id, team_id)]
        funcionarios = await self.funcionario_repo.list_active_by_team(team_id, _MAX_FUNCIONARIOS, 0)
        if not funcionarios:
            raise DomainError("Nenhum funcionario ativo para exportar")
        return funcionarios

    def _dias_do_periodo(self, inicio: date, fim: date) -> list[date]:
        dias = []
        atual = inicio
        while atual <= fim:
            dias.append(atual)
            atual += timedelta(days=1)
        return dias

    def _empresa(self, current_user: User) -> str:
        cnpj = getattr(current_user.team, "cnpj", None)
        titulo = getattr(current_user.team, "title", "") or ""
        return f"{titulo} — CNPJ {cnpj}" if cnpj else titulo

    def _ensure_periodo_valido(self, inicio: date, fim: date) -> None:
        if fim < inicio:
            raise DomainError("Data final deve ser posterior a data inicial")
        if (fim - inicio).days + 1 > _MAX_DIAS:
            raise DomainError("Periodo de exportacao limitado a um ano")

    def _ensure_rh_admin(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")
