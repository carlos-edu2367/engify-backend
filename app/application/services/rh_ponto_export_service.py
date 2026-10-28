"""Exportacao dos registros de ponto no formato de cartao para assinatura."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

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
from app.application.providers.utility.cartao_ponto_builder import (
    CartaoFuncionario,
    CartaoPontoBuilder,
    DiaCartao,
)
from app.core.tempo import day_bounds, local_date_of, local_tz
from app.domain.entities.rh import HorarioTrabalho, RegistroPonto, StatusAtestado, StatusFerias
from app.domain.entities.rh_abono import separar_abonos
from app.domain.entities.rh_calendario import TipoEventoCalendario
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError
from app.domain.services.rh_cartao_ponto import montar_linha
from app.domain.services.rh_ponto_calculo import minutos_liberacao, resultado_dia, _abater_minutos_abonados

_MAX_DIAS = 366
_MAX_FUNCIONARIOS = 500
_EVENTOS_QUE_ABONAM = {
    TipoEventoCalendario.FERIADO,
    TipoEventoCalendario.PONTO_FACULTATIVO,
    TipoEventoCalendario.ABONO,
}


class RhPontoExportService:
    def __init__(
        self,
        funcionario_repo: FuncionarioRepository,
        registro_ponto_repo: RegistroPontoRepository,
        builder: CartaoPontoBuilder | None = None,
        horario_repo: HorarioTrabalhoRepository | None = None,
        abono_repo: AbonoFaltaRepository | None = None,
        ferias_repo: FeriasRepository | None = None,
        atestado_repo: AtestadoRepository | None = None,
        tipo_atestado_repo: TipoAtestadoRepository | None = None,
        evento_calendario_repo: EventoCalendarioRepository | None = None,
    ) -> None:
        self.funcionario_repo = funcionario_repo
        self.registro_ponto_repo = registro_ponto_repo
        self.builder = builder or CartaoPontoBuilder()
        self.horario_repo = horario_repo
        self.abono_repo = abono_repo
        self.ferias_repo = ferias_repo
        self.atestado_repo = atestado_repo
        self.tipo_atestado_repo = tipo_atestado_repo
        self.evento_calendario_repo = evento_calendario_repo

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
        funcionario_ids = [f.id for f in funcionarios]
        registros = await self.registro_ponto_repo.list_by_competencia(
            team_id,
            funcionario_ids,
            janela_inicio,
            janela_fim,
        )

        datas_abonadas_por_func = await self._datas_abonadas_por_funcionario(
            team_id, funcionario_ids, janela_inicio, janela_fim
        )
        minutos_abonados_por_func: dict[UUID, dict[date, Decimal]] = {}
        if self.abono_repo is not None:
            abonos_existentes = await self.abono_repo.list_by_periodo(team_id, inicio, fim)
            datas_abono_manual, minutos_abonados_por_func = separar_abonos(abonos_existentes)
            for func_id, datas in datas_abono_manual.items():
                datas_abonadas_por_func[func_id] |= datas
        eventos = (
            await self.evento_calendario_repo.list_by_periodo(team_id, inicio, fim)
            if self.evento_calendario_repo is not None
            else []
        )

        tz = local_tz()
        por_funcionario_e_dia: dict[tuple[UUID, date], list[RegistroPonto]] = defaultdict(list)
        for registro in registros:
            chave = (registro.funcionario_id, local_date_of(registro.timestamp))
            por_funcionario_e_dia[chave].append(registro)

        horarios = await self._horarios_por_funcionario(team_id, funcionarios)

        dias_do_periodo = self._dias_do_periodo(inicio, fim)
        hoje = datetime.now(tz).date()
        cartoes = []
        for funcionario in funcionarios:
            horario = horarios.get(funcionario.id)
            datas_abonadas = set(datas_abonadas_por_func.get(funcionario.id, set()))
            liberacoes = self._aplicar_eventos(funcionario.id, horario, eventos, datas_abonadas)
            cartoes.append(
                CartaoFuncionario(
                    nome=funcionario.nome,
                    cargo=funcionario.cargo,
                    dias=[
                        self._montar_dia(
                            dia,
                            por_funcionario_e_dia.get((funcionario.id, dia), []),
                            horario,
                            tz,
                            datas_abonadas=datas_abonadas,
                            minutos_abonados=minutos_abonados_por_func.get(funcionario.id, {}),
                            liberacoes=liberacoes,
                            hoje=hoje,
                        )
                        for dia in dias_do_periodo
                    ],
                )
            )

        return self.builder.build(
            empresa=self._empresa(current_user),
            inicio=inicio,
            fim=fim,
            cartoes=cartoes,
        )

    async def _datas_abonadas_por_funcionario(
        self,
        team_id: UUID,
        funcionario_ids: list[UUID],
        janela_inicio: datetime,
        janela_fim: datetime,
    ) -> dict[UUID, set[date]]:
        """Dias de ferias e de atestado que abona falta, pela mesma regra da
        tela de faltas (RhAbonoService.listar_faltas). Sem isso o cartao
        cobrava atraso de um dia que o RH ja tinha resolvido."""
        datas: dict[UUID, set[date]] = defaultdict(set)
        if self.ferias_repo is not None:
            ferias_items = await self.ferias_repo.list_by_competencia(
                team_id, funcionario_ids, janela_inicio, janela_fim,
                statuses={StatusFerias.APROVADO, StatusFerias.EM_ANDAMENTO},
            )
            for ferias in ferias_items:
                self._marcar_intervalo(datas[ferias.funcionario_id], ferias.data_inicio.date(), ferias.data_fim.date())
        if self.atestado_repo is not None and self.tipo_atestado_repo is not None:
            atestados = await self.atestado_repo.list_by_competencia(
                team_id, funcionario_ids, janela_inicio, janela_fim, statuses={StatusAtestado.ENTREGUE}
            )
            abona_por_tipo: dict[UUID, bool] = {}
            for atestado in atestados:
                if atestado.tipo_atestado_id not in abona_por_tipo:
                    tipo = await self.tipo_atestado_repo.get_by_id(atestado.tipo_atestado_id, team_id)
                    abona_por_tipo[atestado.tipo_atestado_id] = tipo.abona_falta
                if abona_por_tipo[atestado.tipo_atestado_id]:
                    self._marcar_intervalo(datas[atestado.funcionario_id], atestado.data_inicio.date(), atestado.data_fim.date())
        return datas

    def _marcar_intervalo(self, datas: set[date], inicio: date, fim: date) -> None:
        dia = inicio
        while dia <= fim:
            datas.add(dia)
            dia += timedelta(days=1)

    def _aplicar_eventos(
        self,
        funcionario_id: UUID,
        horario: HorarioTrabalho | None,
        eventos: list,
        datas_abonadas: set[date],
    ) -> dict[date, Decimal]:
        """Feriado, ponto facultativo e abono de calendario abonam o dia; a
        liberacao antecipada reduz a jornada esperada, como na folha."""
        liberacoes: dict[date, Decimal] = {}
        for evento in eventos:
            if not evento.aplica_a(funcionario_id):
                continue
            if evento.tipo in _EVENTOS_QUE_ABONAM:
                datas_abonadas.add(evento.data)
            elif evento.tipo == TipoEventoCalendario.LIBERACAO_ANTECIPADA and horario is not None:
                turno_dia = horario.turno_para_dia(evento.data.weekday())
                if turno_dia is not None:
                    liberacoes[evento.data] = minutos_liberacao(turno_dia, evento.hora_corte)
        return liberacoes

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
        liberacoes: dict[date, Decimal] | None = None,
        hoje: date | None = None,
    ) -> DiaCartao:
        # Sem horario cadastrado o turno do dia e sempre None; resultado_dia trata isso como
        # esperado=0, entao qualquer batida vira hora extra em vez de sumir do cartao.
        turno = horario.turno_para_dia(dia.weekday()) if horario is not None else None
        datas_abonadas = datas_abonadas or set()
        minutos_abonados = minutos_abonados or {}
        liberacoes = liberacoes or {}

        # Dia que ainda nao chegou nao tem divida: sem isso o cartao do mes
        # corrente saia com a jornada inteira como atraso nos dias futuros.
        if dia in datas_abonadas or (hoje is not None and dia > hoje):
            resultado = resultado_dia(registros_do_dia, turno, esperado_min_override=Decimal("0"))
        else:
            resultado = resultado_dia(registros_do_dia, turno, esperado_min_override=liberacoes.get(dia))
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
