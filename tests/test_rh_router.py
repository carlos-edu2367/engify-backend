from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import Funcionario, HorarioTrabalho, LocalPonto, RegistroPonto, StatusPonto, TipoPonto, TurnoHorario
from app.domain.entities.rh import Holerite, StatusHolerite
from app.domain.entities.team import Plans, Team
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError
from app.http.dependencies.auth import get_current_user
from app.http.dependencies.services import (
    get_rh_dashboard_service,
    get_rh_funcionario_service,
    get_rh_local_ponto_service,
    get_rh_ponto_service,
    get_rh_solicitacoes_service,
    get_storage_provider,
)
from app.http.routers.rh import router


def _make_team(team_id=None) -> Team:
    team = object.__new__(Team)
    team.id = team_id or uuid4()
    team.title = "Engify"
    team.cnpj = "12345678000195"
    team.plan = Plans.PRO
    team.expiration_date = datetime.now(timezone.utc)
    return team


def _make_user(role: Roles, team_id=None) -> User:
    user = object.__new__(User)
    user.id = uuid4()
    user.nome = "Carlos"
    user.email = "carlos@example.com"
    user.senha_hash = "hash"
    user.role = role
    user.team = _make_team(team_id)
    user.cpf = CPF("52998224725")
    return user


class _FakeRhService:
    def __init__(self, funcionario=None, error=None) -> None:
        self.funcionario = funcionario
        self.error = error

    async def create_funcionario(self, dto, current_user):
        if self.error:
            raise self.error
        return self.funcionario

    async def get_funcionario(self, funcionario_id, current_user):
        if self.error:
            raise self.error
        return self.funcionario

    async def list_funcionarios(self, current_user, page, limit, search=None, is_active=None):
        return [self.funcionario], 1

    async def update_funcionario(self, funcionario_id, dto, current_user, reason=None):
        if self.error:
            raise self.error
        return self.funcionario

    async def delete_funcionario(self, funcionario_id, current_user, reason=None):
        if self.error:
            raise self.error
        return None

    async def get_horario(self, funcionario_id, current_user):
        if self.error:
            raise self.error
        return self.funcionario.horario_trabalho

    async def replace_horario(self, funcionario_id, dto, current_user):
        if self.error:
            raise self.error
        return self.funcionario.horario_trabalho


class _FakeLocalPontoService:
    def __init__(self, local=None, error=None) -> None:
        self.local = local
        self.error = error

    async def list_locais(self, funcionario_id, current_user, page, limit):
        if self.error:
            raise self.error
        return [self.local], 1

    async def create_local(self, funcionario_id, dto, current_user):
        if self.error:
            raise self.error
        return self.local

    async def update_local(self, local_id, dto, current_user):
        if self.error:
            raise self.error
        return self.local

    async def delete_local(self, local_id, current_user):
        if self.error:
            raise self.error
        return None


class _FakePontoService:
    def __init__(self, registro=None, error=None) -> None:
        self.registro = registro
        self.error = error

    async def registrar_ponto(self, dto, current_user, request_context):
        if self.error:
            raise self.error
        return self.registro

    async def list_pontos(self, current_user, page, limit, funcionario_id=None, start=None, end=None, status=None):
        if self.error:
            raise self.error
        return [self.registro], 1

    async def list_meus_pontos(self, current_user, page, limit, start=None, end=None, status=None):
        if self.error:
            raise self.error
        return [self.registro], 1


class _FakeSolicitacoesService:
    def __init__(self, ferias=None, ajuste=None, tipo=None, atestado=None, error=None) -> None:
        self.ferias = ferias
        self.ajuste = ajuste
        self.tipo = tipo
        self.atestado = atestado
        self.error = error

    async def request_ferias(self, dto, current_user):
        if self.error:
            raise self.error
        return self.ferias

    async def list_ferias(self, current_user, filters, page, limit):
        return [self.ferias], 1

    async def approve_ferias(self, ferias_id, current_user):
        if self.error:
            raise self.error
        return self.ferias

    async def reject_ferias(self, ferias_id, motivo, current_user):
        if self.error:
            raise self.error
        return self.ferias

    async def cancel_ferias(self, ferias_id, motivo, current_user):
        if self.error:
            raise self.error
        return self.ferias

    async def request_ajuste(self, dto, current_user):
        if self.error:
            raise self.error
        return self.ajuste

    async def list_ajustes(self, current_user, filters, page, limit):
        return [self.ajuste], 1

    async def approve_ajuste(self, ajuste_id, current_user):
        if self.error:
            raise self.error
        return self.ajuste

    async def reject_ajuste(self, ajuste_id, motivo, current_user):
        if self.error:
            raise self.error
        return self.ajuste

    async def create_tipo_atestado(self, dto, current_user):
        if self.error:
            raise self.error
        return self.tipo

    async def list_tipos_atestado(self, current_user, page, limit):
        return [self.tipo], 1

    async def update_tipo_atestado(self, tipo_id, dto, current_user):
        if self.error:
            raise self.error
        return self.tipo

    async def delete_tipo_atestado(self, tipo_id, current_user):
        if self.error:
            raise self.error
        return None

    async def create_atestado(self, dto, current_user):
        if self.error:
            raise self.error
        return self.atestado

    async def list_atestados(self, current_user, filters, page, limit):
        return [self.atestado], 1

    async def deliver_atestado(self, atestado_id, file_path, current_user):
        if self.error:
            raise self.error
        return self.atestado

    async def reject_atestado(self, atestado_id, motivo, current_user):
        if self.error:
            raise self.error
        return self.atestado

    async def obter_atestado_para_download(self, atestado_id, current_user):
        if self.error:
            raise self.error
        return self.atestado


class _FakeFolhaService:
    def __init__(self, holerite=None, error=None) -> None:
        self.holerite = holerite
        self.error = error

    async def gerar_rascunho_folha(self, current_user, mes, ano, funcionario_id=None):
        if self.error:
            raise self.error
        return [self.holerite]

    async def listar_holerites(self, current_user, mes, ano, status, page, limit, funcionario_id=None):
        if self.error:
            raise self.error
        return [self.holerite], 1

    async def obter_holerite(self, holerite_id, current_user):
        if self.error:
            raise self.error
        return self.holerite

    async def atualizar_ajustes_manuais(self, holerite_id, acrescimos, descontos, current_user, reason):
        if self.error:
            raise self.error
        return self.holerite

    async def fechar_folha(self, current_user, mes, ano, funcionario_ids=None, idempotency_key=None):
        if self.error:
            raise self.error
        return [self.holerite]

    async def listar_meus_holerites(self, current_user, page, limit):
        if self.error:
            raise self.error
        return [self.holerite], 1

    async def obter_meu_holerite(self, holerite_id, current_user):
        if self.error:
            raise self.error
        return self.holerite


class _FakeDashboardService:
    def __init__(self, dashboard=None, resumo=None, audit_items=None, error=None) -> None:
        self.dashboard = dashboard
        self.resumo = resumo
        self.audit_items = audit_items or []
        self.error = error

    async def obter_dashboard(self, current_user, mes, ano):
        if self.error:
            raise self.error
        return self.dashboard

    async def obter_meu_resumo(self, current_user):
        if self.error:
            raise self.error
        return self.resumo

    async def listar_audit_logs(self, current_user, page, limit, filters):
        if self.error:
            raise self.error
        return self.audit_items, len(self.audit_items)


class _FakeStorageProvider:
    async def get_signed_download_url(self, bucket, path, expires_in=3600):
        return f"https://signed.example/{path}?expires_in={expires_in}"


def _make_funcionario(team_id):
    funcionario = Funcionario(
        team_id=team_id,
        nome="Ana Souza",
        cpf=CPF("11144477735"),
        cargo="Analista",
        salario_base=Money(Decimal("4500.00")),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    funcionario.horario_trabalho = HorarioTrabalho(
        team_id=team_id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    return funcionario


def _make_local(team_id, funcionario_id):
    return LocalPonto(
        team_id=team_id,
        funcionario_id=funcionario_id,
        nome="Obra Centro",
        latitude=-16.6869,
        longitude=-49.2648,
        raio_metros=100,
    )


def _make_registro(team_id, funcionario_id):
    return RegistroPonto(
        team_id=team_id,
        funcionario_id=funcionario_id,
        tipo=TipoPonto.ENTRADA,
        timestamp=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
        latitude=-16.6869,
        longitude=-49.2648,
        status=StatusPonto.VALIDADO,
    )


def _make_ferias(team_id, funcionario_id):
    from app.domain.entities.rh import Ferias

    return Ferias(
        team_id=team_id,
        funcionario_id=funcionario_id,
        data_inicio=datetime(2026, 5, 1, tzinfo=timezone.utc),
        data_fim=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )


def _make_ajuste(team_id, funcionario_id):
    from app.domain.entities.rh import AjustePonto

    return AjustePonto(
        team_id=team_id,
        funcionario_id=funcionario_id,
        data_referencia=datetime(2026, 4, 28, tzinfo=timezone.utc),
        justificativa="Esqueci",
        hora_entrada_solicitada=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
    )


def _make_tipo_atestado(team_id):
    from app.domain.entities.rh import TipoAtestado

    return TipoAtestado(team_id=team_id, nome="Medico", prazo_entrega_dias=2, abona_falta=True)


def _make_atestado(team_id, funcionario_id, tipo_id):
    from app.domain.entities.rh import Atestado

    return Atestado(
        team_id=team_id,
        funcionario_id=funcionario_id,
        tipo_atestado_id=tipo_id,
        data_inicio=datetime(2026, 4, 28, tzinfo=timezone.utc),
        data_fim=datetime(2026, 4, 29, tzinfo=timezone.utc),
    )


def _make_holerite(team_id, funcionario_id):
    return Holerite(
        team_id=team_id,
        funcionario_id=funcionario_id,
        mes_referencia=4,
        ano_referencia=2026,
        salario_base=Money(Decimal("4500.00")),
        horas_extras=Money(Decimal("120.00")),
        descontos_falta=Money(Decimal("0.00")),
        acrescimos_manuais=Money(Decimal("50.00")),
        descontos_manuais=Money(Decimal("25.00")),
        valor_liquido=Money(Decimal("4645.00")),
        status=StatusHolerite.RASCUNHO,
    )


def _build_client(
    user,
    service,
    local_service=None,
    ponto_service=None,
    solicitacoes_service=None,
    folha_service=None,
    dashboard_service=None,
    storage_provider=None,
):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_rh_funcionario_service] = lambda: service
    app.dependency_overrides[get_rh_local_ponto_service] = lambda: local_service or _FakeLocalPontoService()
    app.dependency_overrides[get_rh_ponto_service] = lambda: ponto_service or _FakePontoService()
    app.dependency_overrides[get_rh_solicitacoes_service] = lambda: solicitacoes_service or _FakeSolicitacoesService()
    from app.http.dependencies.services import get_rh_folha_service

    app.dependency_overrides[get_rh_folha_service] = lambda: folha_service or _FakeFolhaService()
    app.dependency_overrides[get_rh_dashboard_service] = lambda: dashboard_service or _FakeDashboardService()
    app.dependency_overrides[get_storage_provider] = lambda: storage_provider or _FakeStorageProvider()
    return TestClient(app)


def test_create_funcionario_route_returns_201_and_masked_cpf():
    admin = _make_user(Roles.ADMIN)
    client = _build_client(admin, _FakeRhService(funcionario=_make_funcionario(admin.team.id)))

    response = client.post(
        "/rh/funcionarios",
        json={
            "nome": "Ana Souza",
            "cpf": "11144477735",
            "cargo": "Analista",
            "salario_base": "4500.00",
            "data_admissao": "2026-04-01",
            "user_id": None,
            "horario_trabalho": {
                "turnos": [{"dia_semana": 0, "hora_entrada": "08:00:00", "hora_saida": "17:00:00"}]
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["cpf_mascarado"] == "111.***.***-35"


def test_create_funcionario_route_returns_403_for_funcionario_role():
    employee = _make_user(Roles.FUNCIONARIO)
    client = _build_client(employee, _FakeRhService(funcionario=_make_funcionario(employee.team.id)))

    response = client.get("/rh/funcionarios")

    assert response.status_code == 403


def test_create_funcionario_route_maps_duplicate_cpf_to_409():
    admin = _make_user(Roles.ADMIN)
    client = _build_client(
        admin,
        _FakeRhService(error=DomainError("Ja existe um funcionario com esse CPF neste time")),
    )

    response = client.post(
        "/rh/funcionarios",
        json={
            "nome": "Ana Souza",
            "cpf": "11144477735",
            "cargo": "Analista",
            "salario_base": "4500.00",
            "data_admissao": "2026-04-01",
            "user_id": None,
            "horario_trabalho": {
                "turnos": [{"dia_semana": 0, "hora_entrada": "08:00:00", "hora_saida": "17:00:00"}]
            },
        },
    )

    assert response.status_code == 409


def test_get_funcionario_route_maps_cross_tenant_lookup_to_404():
    admin = _make_user(Roles.ADMIN)
    client = _build_client(admin, _FakeRhService(error=DomainError("Funcionario nao encontrado")))

    response = client.get(f"/rh/funcionarios/{uuid4()}")

    assert response.status_code == 404


def test_create_local_ponto_route_returns_201():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    local = _make_local(admin.team.id, funcionario.id)
    client = _build_client(
        admin,
        _FakeRhService(funcionario=funcionario),
        local_service=_FakeLocalPontoService(local=local),
    )

    response = client.post(
        f"/rh/funcionarios/{funcionario.id}/locais-ponto",
        json={
            "nome": "Obra Centro",
            "latitude": -16.6869,
            "longitude": -49.2648,
            "raio_metros": 100,
        },
    )

    assert response.status_code == 201
    assert response.json()["nome"] == "Obra Centro"


def test_post_rh_ponto_route_returns_400_for_geofence_denial():
    employee = _make_user(Roles.FUNCIONARIO)
    client = _build_client(
        employee,
        _FakeRhService(funcionario=_make_funcionario(employee.team.id)),
        ponto_service=_FakePontoService(error=DomainError("Voce esta fora de um local autorizado para registrar ponto.")),
    )

    response = client.post(
        "/rh/ponto",
        json={
            "tipo": "entrada",
            "latitude": -16.7000,
            "longitude": -49.3000,
        },
    )

    assert response.status_code == 400


def test_get_meu_ponto_route_returns_403_for_admin():
    admin = _make_user(Roles.ADMIN)
    client = _build_client(
        admin,
        _FakeRhService(funcionario=_make_funcionario(admin.team.id)),
        ponto_service=_FakePontoService(registro=_make_registro(admin.team.id, uuid4())),
    )

    response = client.get("/rh/me/ponto")

    assert response.status_code == 403


def test_list_meu_ponto_route_accepts_period_and_status_filters():
    employee = _make_user(Roles.FUNCIONARIO)
    registro = _make_registro(employee.team.id, uuid4())
    client = _build_client(
        employee,
        _FakeRhService(funcionario=_make_funcionario(employee.team.id)),
        ponto_service=_FakePontoService(registro=registro),
    )

    response = client.get(
        "/rh/me/ponto",
        params={"start": "2026-04-01T00:00:00Z", "end": "2026-04-30T23:59:59Z", "status": "validado"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "validado"


def test_post_ferias_route_returns_200_for_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(employee.team.id)
    ferias = _make_ferias(employee.team.id, funcionario.id)
    client = _build_client(
        employee,
        _FakeRhService(funcionario=funcionario),
        solicitacoes_service=_FakeSolicitacoesService(ferias=ferias),
    )

    response = client.post(
        "/rh/ferias",
        json={"data_inicio": "2026-05-01T00:00:00Z", "data_fim": "2026-05-10T00:00:00Z"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "solicitado"


def test_list_ferias_route_accepts_status_and_period_filters():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    ferias = _make_ferias(admin.team.id, funcionario.id)
    client = _build_client(
        admin,
        _FakeRhService(funcionario=funcionario),
        solicitacoes_service=_FakeSolicitacoesService(ferias=ferias),
    )

    response = client.get(
        "/rh/ferias",
        params={
            "funcionario_id": str(funcionario.id),
            "status": "solicitado",
            "start": "2026-05-01T00:00:00Z",
            "end": "2026-05-31T23:59:59Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "solicitado"


def test_approve_ajuste_route_returns_403_for_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(employee.team.id)
    ajuste = _make_ajuste(employee.team.id, funcionario.id)
    client = _build_client(
        employee,
        _FakeRhService(funcionario=funcionario),
        solicitacoes_service=_FakeSolicitacoesService(ajuste=ajuste),
    )

    response = client.post(f"/rh/ajustes-ponto/{ajuste.id}/aprovar")

    assert response.status_code == 403


def test_create_tipo_atestado_route_returns_201_for_admin():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    tipo = _make_tipo_atestado(admin.team.id)
    client = _build_client(
        admin,
        _FakeRhService(funcionario=funcionario),
        solicitacoes_service=_FakeSolicitacoesService(tipo=tipo),
    )

    response = client.post(
        "/rh/tipos-atestado",
        json={"nome": "Medico", "prazo_entrega_dias": 2, "abona_falta": True},
    )

    assert response.status_code == 201
    assert response.json()["nome"] == "Medico"


def test_create_atestado_route_rejects_manual_file_path():
    employee = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(employee.team.id)
    tipo = _make_tipo_atestado(employee.team.id)
    atestado = _make_atestado(employee.team.id, funcionario.id, tipo.id)
    atestado.file_path = "private/medical.pdf"
    client = _build_client(
        employee,
        _FakeRhService(funcionario=funcionario),
        solicitacoes_service=_FakeSolicitacoesService(atestado=atestado),
    )

    response = client.post(
        "/rh/atestados",
        json={
            "tipo_atestado_id": str(tipo.id),
            "data_inicio": "2026-04-28T00:00:00Z",
            "data_fim": "2026-04-29T00:00:00Z",
            "file_path": "private/medical.pdf",
        },
    )

    assert response.status_code == 422


def test_get_atestado_download_url_route_returns_signed_url():
    employee = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(employee.team.id)
    tipo = _make_tipo_atestado(employee.team.id)
    atestado = _make_atestado(employee.team.id, funcionario.id, tipo.id)
    atestado.file_path = "rh/atestados/medical.pdf"
    client = _build_client(
        employee,
        _FakeRhService(funcionario=funcionario),
        solicitacoes_service=_FakeSolicitacoesService(atestado=atestado),
    )

    response = client.get(f"/rh/atestados/{atestado.id}/download-url")

    assert response.status_code == 200
    assert response.json()["download_url"].startswith("https://signed.example/rh/atestados/medical.pdf")
    assert response.json()["expires_in"] == 3600


def test_list_folha_route_returns_holerites_for_rh_admin():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    holerite = _make_holerite(admin.team.id, funcionario.id)
    client = _build_client(
        admin,
        _FakeRhService(funcionario=funcionario),
        folha_service=_FakeFolhaService(holerite=holerite),
    )

    response = client.get("/rh/folha", params={"mes": 4, "ano": 2026})

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "rascunho"
    assert response.json()["items"][0]["valor_liquido"] == "4645.00"


def test_get_meu_holerite_route_returns_403_for_admin():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    holerite = _make_holerite(admin.team.id, funcionario.id)
    client = _build_client(
        admin,
        _FakeRhService(funcionario=funcionario),
        folha_service=_FakeFolhaService(holerite=holerite),
    )

    response = client.get(f"/rh/me/holerites/{holerite.id}")

    assert response.status_code == 403


def test_get_dashboard_route_returns_summary_for_rh_admin():
    admin = _make_user(Roles.ADMIN)
    client = _build_client(
        admin,
        _FakeRhService(funcionario=_make_funcionario(admin.team.id)),
        dashboard_service=_FakeDashboardService(
            dashboard={
                "mes": 4,
                "ano": 2026,
                "total_funcionarios_ativos": 12,
                "ajustes_pendentes": 3,
                "ferias_em_andamento": 1,
                "atestados_aguardando": 2,
                "atestados_vencidos": 1,
                "pontos_negados_periodo": 4,
                "pontos_inconsistentes_periodo": 2,
                "holerites_rascunho": 5,
                "holerites_fechados": 7,
                "total_liquido_competencia": "25400.00",
            }
        ),
    )

    response = client.get("/rh/dashboard", params={"mes": 4, "ano": 2026})

    assert response.status_code == 200
    assert response.json()["total_funcionarios_ativos"] == 12
    assert response.json()["total_liquido_competencia"] == "25400.00"


def test_get_dashboard_route_returns_403_for_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    client = _build_client(
        employee,
        _FakeRhService(funcionario=_make_funcionario(employee.team.id)),
    )

    response = client.get("/rh/dashboard", params={"mes": 4, "ano": 2026})

    assert response.status_code == 403


def test_get_meu_resumo_route_returns_200_for_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    client = _build_client(
        employee,
        _FakeRhService(funcionario=_make_funcionario(employee.team.id)),
        dashboard_service=_FakeDashboardService(
            resumo={
                "ultimo_ponto": {
                    "tipo": "entrada",
                    "status": "validado",
                    "timestamp": "2026-04-28T08:00:00Z",
                },
                "ajustes_pendentes": 1,
                "ferias_pendentes": 1,
                "atestados_pendentes": 1,
                "ultimo_holerite_fechado": {
                    "mes_referencia": 4,
                    "ano_referencia": 2026,
                    "valor_liquido": "4645.00",
                    "status": "fechado",
                },
            }
        ),
    )

    response = client.get("/rh/me/resumo")

    assert response.status_code == 200
    assert response.json()["ajustes_pendentes"] == 1
    assert response.json()["ultimo_holerite_fechado"]["status"] == "fechado"


def test_get_audit_logs_route_returns_paginated_response_for_admin():
    admin = _make_user(Roles.ADMIN)
    client = _build_client(
        admin,
        _FakeRhService(funcionario=_make_funcionario(admin.team.id)),
        dashboard_service=_FakeDashboardService(
            audit_items=[
                {
                    "id": str(uuid4()),
                    "entity_type": "holerite",
                    "entity_id": str(uuid4()),
                    "action": "rh.holerite.closed",
                    "actor_user_id": str(admin.id),
                    "actor_role": "admin",
                    "reason": None,
                    "before": None,
                    "after": {"valor_liquido": "***"},
                    "request_id": "req-123",
                    "ip_hash": "masked",
                    "user_agent": "pytest",
                    "created_at": "2026-04-29T00:00:00Z",
                }
            ]
        ),
    )

    response = client.get(
        "/rh/audit-logs",
        params={
            "page": 1,
            "limit": 20,
            "action": "rh.holerite.closed",
            "start": "2026-04-01T00:00:00Z",
            "end": "2026-04-30T23:59:59Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["action"] == "rh.holerite.closed"


def test_get_audit_logs_route_returns_403_for_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    client = _build_client(
        employee,
        _FakeRhService(funcionario=_make_funcionario(employee.team.id)),
    )

    response = client.get("/rh/audit-logs")

    assert response.status_code == 403
