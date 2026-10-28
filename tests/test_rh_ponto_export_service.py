from datetime import date, datetime, time, timezone
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from app.application.services.rh_ponto_export_service import RhPontoExportService
from app.domain.entities.rh import (
    Ferias,
    HorarioTrabalho,
    RegistroPonto,
    StatusAtestado,
    StatusFerias,
    StatusPonto,
    TipoPonto,
    TurnoHorario,
)
from app.domain.entities.rh_abono import AbonoFalta
from app.domain.entities.rh_calendario import EventoCalendarioRh, TipoEventoCalendario
from app.domain.entities.user import Roles
from app.domain.errors import DomainError


class _FakeFuncionarioRepo:
    def __init__(self, funcionarios):
        self._funcionarios = funcionarios

    async def get_by_id(self, id, team_id):
        return next(f for f in self._funcionarios if f.id == id)

    async def list_active_by_team(self, team_id, limit, offset):
        return self._funcionarios if offset == 0 else []


class _FakeHorarioRepo:
    def __init__(self, horarios: dict | None = None) -> None:
        self._horarios = horarios or {}

    async def list_by_funcionarios(self, team_id, funcionario_ids):
        return {fid: h for fid, h in self._horarios.items() if fid in funcionario_ids}


class _FakeRegistroRepo:
    def __init__(self, registros):
        self._registros = registros
        self.ultima_janela = None

    async def list_by_competencia(self, team_id, funcionario_ids, start, end):
        self.ultima_janela = (start, end)
        return [r for r in self._registros if r.funcionario_id in funcionario_ids]


class _FakeAbonoRepo:
    def __init__(self, abonos=None):
        self._abonos = abonos or []

    async def list_by_periodo(self, team_id, start, end):
        return [a for a in self._abonos if start <= a.data <= end]


class _FakeFeriasRepo:
    def __init__(self, ferias=None):
        self._ferias = ferias or []

    async def list_by_competencia(self, team_id, funcionario_ids, start, end, statuses):
        return [f for f in self._ferias if f.funcionario_id in funcionario_ids and f.status in statuses]


class _FakeAtestadoRepo:
    def __init__(self, atestados=None):
        self._atestados = atestados or []

    async def list_by_competencia(self, team_id, funcionario_ids, start, end, statuses):
        return [a for a in self._atestados if a.funcionario_id in funcionario_ids and a.status in statuses]


class _FakeTipoAtestadoRepo:
    def __init__(self, tipos=None):
        self._tipos = tipos or {}

    async def get_by_id(self, id, team_id):
        return self._tipos[id]


class _FakeEventoRepo:
    def __init__(self, eventos=None):
        self._eventos = eventos or []

    async def list_by_periodo(self, team_id, start, end):
        return [e for e in self._eventos if start <= e.data <= end]


def _funcionario(nome, cargo):
    return SimpleNamespace(id=uuid4(), nome=nome, cargo=cargo)


def _user(team_id, role=Roles.ADMIN):
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        team=SimpleNamespace(id=team_id, title="Arcaika Ltda", cnpj="00000000000100"),
    )


def _reg(funcionario_id, team_id, momento, tipo):
    return RegistroPonto(
        team_id=team_id,
        funcionario_id=funcionario_id,
        tipo=tipo,
        timestamp=momento,
        latitude=0.0,
        longitude=0.0,
        status=StatusPonto.VALIDADO,
    )


def _service(funcionarios, registros, horarios=None, abonos=None, ferias=None, atestados=None, tipos_atestado=None, eventos=None):
    return RhPontoExportService(
        funcionario_repo=_FakeFuncionarioRepo(funcionarios),
        registro_ponto_repo=_FakeRegistroRepo(registros),
        horario_repo=_FakeHorarioRepo(horarios),
        abono_repo=_FakeAbonoRepo(abonos),
        ferias_repo=_FakeFeriasRepo(ferias),
        atestado_repo=_FakeAtestadoRepo(atestados),
        tipo_atestado_repo=_FakeTipoAtestadoRepo(tipos_atestado),
        evento_calendario_repo=_FakeEventoRepo(eventos),
    )


def _horario_segunda(team_id, funcionario_id):
    # 2026-03-02 e segunda; turno de 9h sem intervalo cadastrado.
    return HorarioTrabalho(
        team_id=team_id,
        funcionario_id=funcionario_id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )


async def _celula(service, team_id, funcionario, celula, inicio=date(2026, 3, 1), fim=date(2026, 3, 31)):
    conteudo = await service.exportar_cartoes(_user(team_id), inicio, fim, funcionario_id=funcionario.id)
    return load_workbook(BytesIO(conteudo)).worksheets[0][celula].value


@pytest.mark.asyncio
async def test_exporta_uma_aba_por_funcionario_ativo():
    team_id = uuid4()
    funcionarios = [_funcionario("Sandro Barbosa", "Serralheiro"), _funcionario("Ana Lima", "Pedreira")]
    service = _service(funcionarios, [])
    conteudo = await service.exportar_cartoes(
        _user(team_id), date(2026, 3, 1), date(2026, 3, 31), funcionario_id=None
    )
    nomes = load_workbook(BytesIO(conteudo)).sheetnames
    assert nomes == ["Sandro Barbosa", "Ana Lima"]


@pytest.mark.asyncio
async def test_filtra_por_funcionario_quando_informado():
    team_id = uuid4()
    funcionarios = [_funcionario("Sandro Barbosa", "Serralheiro"), _funcionario("Ana Lima", "Pedreira")]
    service = _service(funcionarios, [])
    conteudo = await service.exportar_cartoes(
        _user(team_id), date(2026, 3, 1), date(2026, 3, 31), funcionario_id=funcionarios[1].id
    )
    assert load_workbook(BytesIO(conteudo)).sheetnames == ["Ana Lima"]


@pytest.mark.asyncio
async def test_batida_noturna_cai_no_dia_local_correto():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    # 10/03 as 18:00 e 23:00 locais; a saida em UTC ja e 11/03 as 02:00.
    registros = [
        _reg(funcionario.id, team_id, datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc), TipoPonto.ENTRADA),
        _reg(funcionario.id, team_id, datetime(2026, 3, 11, 2, 0, tzinfo=timezone.utc), TipoPonto.SAIDA),
    ]
    service = _service([funcionario], registros)
    conteudo = await service.exportar_cartoes(
        _user(team_id), date(2026, 3, 1), date(2026, 3, 31), funcionario_id=funcionario.id
    )
    aba = load_workbook(BytesIO(conteudo)).worksheets[0]
    # Linha 6 e o cabecalho; 01/03 e a linha 7, entao 10/03 e a linha 16.
    assert aba["A16"].value == "10/03/2026"
    assert aba["C16"].value == "18:00"
    assert aba["F16"].value == "23:00"


@pytest.mark.asyncio
async def test_sem_horario_cadastrado_batida_conta_como_hora_extra():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    registros = [
        _reg(funcionario.id, team_id, datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc), TipoPonto.ENTRADA),
        _reg(funcionario.id, team_id, datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc), TipoPonto.SAIDA),
    ]
    service = _service([funcionario], registros)  # sem horario cadastrado
    conteudo = await service.exportar_cartoes(
        _user(team_id), date(2026, 3, 1), date(2026, 3, 31), funcionario_id=funcionario.id
    )
    aba = load_workbook(BytesIO(conteudo)).worksheets[0]
    # 02/03 e a linha 8 (cabecalho na 6, 01/03 na 7)
    assert aba["G8"].value == "04:00"
    assert aba["H8"].value == "00:00"


@pytest.mark.asyncio
async def test_com_turno_cadastrado_jornada_curta_vira_atraso():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    horario = HorarioTrabalho(
        team_id=team_id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],  # 2026-03-02 e segunda
    )
    registros = [
        _reg(funcionario.id, team_id, datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc), TipoPonto.ENTRADA),
        _reg(funcionario.id, team_id, datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc), TipoPonto.SAIDA),
    ]
    service = _service([funcionario], registros, horarios={funcionario.id: horario})
    conteudo = await service.exportar_cartoes(
        _user(team_id), date(2026, 3, 1), date(2026, 3, 31), funcionario_id=funcionario.id
    )
    aba = load_workbook(BytesIO(conteudo)).worksheets[0]
    assert aba["G8"].value == "00:00"
    assert aba["H8"].value == "02:00"


@pytest.mark.asyncio
async def test_recusa_periodo_invertido():
    service = _service([], [])
    with pytest.raises(DomainError):
        await service.exportar_cartoes(
            _user(uuid4()), date(2026, 3, 31), date(2026, 3, 1), funcionario_id=None
        )


@pytest.mark.asyncio
async def test_recusa_periodo_maior_que_um_ano():
    service = _service([], [])
    with pytest.raises(DomainError):
        await service.exportar_cartoes(
            _user(uuid4()), date(2025, 1, 1), date(2026, 6, 1), funcionario_id=None
        )


@pytest.mark.asyncio
async def test_recusa_usuario_sem_perfil_de_rh():
    service = _service([], [])
    with pytest.raises(DomainError):
        await service.exportar_cartoes(
            _user(uuid4(), role=Roles.FUNCIONARIO), date(2026, 3, 1), date(2026, 3, 31), funcionario_id=None
        )


def test_nome_arquivo_usa_o_periodo():
    service = _service([], [])
    assert service.nome_arquivo(date(2026, 3, 1), date(2026, 3, 31)) == "cartoes-ponto-2026-03-01-a-2026-03-31.xlsx"


@pytest.mark.asyncio
async def test_abono_dia_inteiro_remove_falta_do_cartao():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    horario = HorarioTrabalho(
        team_id=team_id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],  # 2026-03-02 e segunda
    )
    registros = []  # sem registro de ponto, seria falta
    abono = AbonoFalta(
        team_id=team_id,
        funcionario_id=funcionario.id,
        data=date(2026, 3, 2),
        motivo="Abono teste",
    )
    service = _service([funcionario], registros, horarios={funcionario.id: horario}, abonos=[abono])
    conteudo = await service.exportar_cartoes(
        _user(team_id), date(2026, 3, 1), date(2026, 3, 31), funcionario_id=funcionario.id
    )
    aba = load_workbook(BytesIO(conteudo)).worksheets[0]
    assert aba["H8"].value == "00:00", "Dia abonado nao deve ter falta"


@pytest.mark.asyncio
async def test_abono_parcial_abate_horas_do_cartao():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    horario = HorarioTrabalho(
        team_id=team_id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],  # 2026-03-02 e segunda
    )
    registros = [
        _reg(funcionario.id, team_id, datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc), TipoPonto.ENTRADA),
        _reg(funcionario.id, team_id, datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc), TipoPonto.SAIDA),
    ]  # saiu 1 hora antes: 2 horas de falta normalmente
    abono = AbonoFalta(
        team_id=team_id,
        funcionario_id=funcionario.id,
        data=date(2026, 3, 2),
        motivo="Abono parcial",
        minutos=60,  # abona 1 hora das 2 de falta
    )
    service = _service([funcionario], registros, horarios={funcionario.id: horario}, abonos=[abono])
    conteudo = await service.exportar_cartoes(
        _user(team_id), date(2026, 3, 1), date(2026, 3, 31), funcionario_id=funcionario.id
    )
    aba = load_workbook(BytesIO(conteudo)).worksheets[0]
    assert aba["H8"].value == "01:00", "Abono parcial deve abater 1 hora das 2 de falta"


@pytest.mark.asyncio
async def test_feriado_do_calendario_nao_vira_atraso():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    feriado = EventoCalendarioRh(team_id=team_id, tipo=TipoEventoCalendario.FERIADO, data=date(2026, 3, 2), descricao="Feriado")
    service = _service([funcionario], [], horarios={funcionario.id: _horario_segunda(team_id, funcionario.id)}, eventos=[feriado])
    assert await _celula(service, team_id, funcionario, "H8") == "00:00"


@pytest.mark.asyncio
async def test_evento_de_outro_funcionario_nao_abona():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    abono = EventoCalendarioRh(
        team_id=team_id, tipo=TipoEventoCalendario.ABONO, data=date(2026, 3, 2), descricao="Abono",
        aplica_todos=False, funcionario_ids=[uuid4()],
    )
    service = _service([funcionario], [], horarios={funcionario.id: _horario_segunda(team_id, funcionario.id)}, eventos=[abono])
    assert await _celula(service, team_id, funcionario, "H8") == "09:00"


@pytest.mark.asyncio
async def test_liberacao_antecipada_reduz_jornada_esperada():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    liberacao = EventoCalendarioRh(
        team_id=team_id, tipo=TipoEventoCalendario.LIBERACAO_ANTECIPADA, data=date(2026, 3, 2),
        descricao="Liberados as 15h", hora_corte=time(15, 0),
    )
    registros = [
        _reg(funcionario.id, team_id, datetime(2026, 3, 2, 11, 0, tzinfo=timezone.utc), TipoPonto.ENTRADA),  # 08:00 local
        _reg(funcionario.id, team_id, datetime(2026, 3, 2, 18, 0, tzinfo=timezone.utc), TipoPonto.SAIDA),  # 15:00 local
    ]
    service = _service([funcionario], registros, horarios={funcionario.id: _horario_segunda(team_id, funcionario.id)}, eventos=[liberacao])
    assert await _celula(service, team_id, funcionario, "H8") == "00:00"


@pytest.mark.asyncio
async def test_ferias_aprovadas_nao_viram_atraso():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    ferias = Ferias(
        team_id=team_id, funcionario_id=funcionario.id,
        data_inicio=datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc), data_fim=datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc),
        status=StatusFerias.APROVADO,
    )
    service = _service([funcionario], [], horarios={funcionario.id: _horario_segunda(team_id, funcionario.id)}, ferias=[ferias])
    assert await _celula(service, team_id, funcionario, "H8") == "00:00"


@pytest.mark.asyncio
async def test_atestado_que_abona_remove_atraso_e_o_que_nao_abona_mantem():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    tipo_abona, tipo_nao_abona = uuid4(), uuid4()
    atestados = [
        SimpleNamespace(
            funcionario_id=funcionario.id, tipo_atestado_id=tipo_abona, status=StatusAtestado.ENTREGUE,
            data_inicio=datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc), data_fim=datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            funcionario_id=funcionario.id, tipo_atestado_id=tipo_nao_abona, status=StatusAtestado.ENTREGUE,
            data_inicio=datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc), data_fim=datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc),
        ),
    ]
    tipos = {tipo_abona: SimpleNamespace(abona_falta=True), tipo_nao_abona: SimpleNamespace(abona_falta=False)}
    service = _service(
        [funcionario], [], horarios={funcionario.id: _horario_segunda(team_id, funcionario.id)},
        atestados=atestados, tipos_atestado=tipos,
    )
    assert await _celula(service, team_id, funcionario, "H8") == "00:00"
    assert await _celula(service, team_id, funcionario, "H15") == "09:00"  # 09/03


@pytest.mark.asyncio
async def test_dia_futuro_nao_vira_atraso():
    team_id = uuid4()
    funcionario = _funcionario("Sandro Barbosa", "Serralheiro")
    horario = HorarioTrabalho(
        team_id=team_id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=d, hora_entrada=time(8, 0), hora_saida=time(17, 0)) for d in range(7)],
    )
    service = _service([funcionario], [], horarios={funcionario.id: horario})
    assert await _celula(service, team_id, funcionario, "H7", inicio=date(2099, 3, 1), fim=date(2099, 3, 31)) == "00:00"
