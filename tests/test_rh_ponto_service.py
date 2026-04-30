from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    Funcionario,
    HorarioTrabalho,
    LocalPonto,
    RegistroPonto,
    RhAuditLog,
    StatusPonto,
    TipoPonto,
    TurnoHorario,
)
from app.domain.entities.team import Plans, Team
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError


def _make_team(team_id=None) -> Team:
    team = object.__new__(Team)
    team.id = team_id or uuid4()
    team.title = "Engify"
    team.cnpj = "12345678000195"
    team.plan = Plans.PRO
    team.expiration_date = datetime.now(timezone.utc)
    return team


def _make_user(role: Roles, team_id=None, user_id=None) -> User:
    user = object.__new__(User)
    user.id = user_id or uuid4()
    user.nome = "Carlos"
    user.email = "carlos@example.com"
    user.senha_hash = "hash"
    user.role = role
    user.team = _make_team(team_id)
    user.cpf = CPF("52998224725")
    return user


def _make_funcionario(team_id, user_id=None, is_active=True) -> Funcionario:
    funcionario = Funcionario(
        team_id=team_id,
        nome="Ana Souza",
        cpf=CPF("11144477735"),
        cargo="Analista",
        salario_base=Money(Decimal("4500.00")),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
        user_id=user_id,
        is_active=is_active,
    )
    funcionario.horario_trabalho = HorarioTrabalho(
        team_id=team_id,
        funcionario_id=funcionario.id,
        turnos=[
            TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0)),
        ],
    )
    return funcionario


class _FakeFuncionarioRepo:
    def __init__(self, funcionarios=None) -> None:
        self.by_id = {funcionario.id: funcionario for funcionario in funcionarios or []}

    async def get_by_id(self, id, team_id):
        funcionario = self.by_id.get(id)
        if not funcionario or funcionario.team_id != team_id or funcionario.is_deleted:
            raise DomainError("Funcionario nao encontrado")
        return funcionario

    async def get_by_cpf(self, team_id, cpf):
        return None

    async def get_by_user_id(self, team_id, user_id):
        for funcionario in self.by_id.values():
            if funcionario.team_id == team_id and funcionario.user_id == user_id and not funcionario.is_deleted:
                return funcionario
        return None

    async def list_by_team(self, team_id, page, limit, search=None, is_active=None):
        return []

    async def count_by_team(self, team_id, search=None, is_active=None):
        return 0

    async def save(self, funcionario):
        self.by_id[funcionario.id] = funcionario
        return funcionario


class _FakeLocalPontoRepo:
    def __init__(self, locais=None) -> None:
        self.by_id = {local.id: local for local in locais or []}

    async def get_by_id(self, id, team_id):
        local = self.by_id.get(id)
        if not local or local.team_id != team_id or local.is_deleted:
            raise DomainError("Local de ponto nao encontrado")
        return local

    async def list_by_team(self, team_id, page, limit):
        items = [local for local in self.by_id.values() if local.team_id == team_id and not local.is_deleted]
        return items[(page - 1) * limit : page * limit]

    async def list_by_funcionario(self, team_id, funcionario_id):
        return [
            local
            for local in self.by_id.values()
            if local.team_id == team_id and local.funcionario_id == funcionario_id and not local.is_deleted
        ]

    async def save(self, local_ponto):
        self.by_id[local_ponto.id] = local_ponto
        return local_ponto


class _FakeRegistroPontoRepo:
    def __init__(self, registros=None) -> None:
        self.items = list(registros or [])

    async def get_by_id(self, id, team_id):
        for registro in self.items:
            if registro.id == id and registro.team_id == team_id and not registro.is_deleted:
                return registro
        raise DomainError("Registro de ponto nao encontrado")

    async def list_by_team(self, team_id, page, limit):
        registros = [item for item in self.items if item.team_id == team_id and not item.is_deleted]
        return registros[(page - 1) * limit : page * limit]

    async def count_by_team(self, team_id):
        return len([item for item in self.items if item.team_id == team_id and not item.is_deleted])

    async def list_by_team_periodo(self, team_id, start, end, status=None, page=1, limit=50):
        registros = [
            item
            for item in self.items
            if item.team_id == team_id and start <= item.timestamp <= end and not item.is_deleted
        ]
        if status is not None:
            registros = [item for item in registros if item.status == status]
        return registros[(page - 1) * limit : page * limit]

    async def list_by_funcionario_periodo(self, team_id, funcionario_id, start, end, status=None, page=1, limit=50):
        registros = [
            item
            for item in self.items
            if item.team_id == team_id
            and item.funcionario_id == funcionario_id
            and start <= item.timestamp <= end
            and not item.is_deleted
        ]
        if status is not None:
            registros = [item for item in registros if item.status == status]
        return registros[(page - 1) * limit : page * limit]

    async def count_by_funcionario_periodo(self, team_id, funcionario_id, start, end, status=None):
        registros = [
            item
            for item in self.items
            if item.team_id == team_id
            and item.funcionario_id == funcionario_id
            and start <= item.timestamp <= end
            and not item.is_deleted
        ]
        if status is not None:
            registros = [item for item in registros if item.status == status]
        return len(registros)

    async def get_last_valid_by_funcionario(self, team_id, funcionario_id):
        validos = [
            item
            for item in self.items
            if item.team_id == team_id
            and item.funcionario_id == funcionario_id
            and item.status in {StatusPonto.VALIDADO, StatusPonto.INCONSISTENTE, StatusPonto.AJUSTADO}
            and not item.is_deleted
        ]
        validos.sort(key=lambda item: item.timestamp, reverse=True)
        return validos[0] if validos else None

    async def get_last_valid_on_day(self, team_id, funcionario_id, day_start, day_end):
        validos = [
            item
            for item in self.items
            if item.team_id == team_id
            and item.funcionario_id == funcionario_id
            and day_start <= item.timestamp <= day_end
            and item.status in {StatusPonto.VALIDADO, StatusPonto.INCONSISTENTE, StatusPonto.AJUSTADO}
            and not item.is_deleted
        ]
        validos.sort(key=lambda item: item.timestamp, reverse=True)
        return validos[0] if validos else None

    async def save(self, registro):
        self.items.append(registro)
        return registro

    async def count_by_team_periodo(self, team_id, start, end, status=None):
        registros = await self.list_by_team_periodo(team_id, start, end, status=status, page=1, limit=10_000)
        return len(registros)

    async def list_by_funcionario_day(self, team_id, funcionario_id, day_start, day_end):
        return [
            item
            for item in self.items
            if item.team_id == team_id
            and item.funcionario_id == funcionario_id
            and day_start <= item.timestamp <= day_end
            and not item.is_deleted
        ]


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.events: list[RhAuditLog] = []

    async def save(self, audit_log):
        self.events.append(audit_log)
        return audit_log


class _FakeIdempotencyRepo:
    def __init__(self) -> None:
        self.keys = set()

    async def exists_or_create(self, team_id, scope, key):
        item = (str(team_id), scope, key)
        if item in self.keys:
            return True
        self.keys.add(item)
        return False


class _FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


class _FakeGeofenceCache:
    def __init__(self) -> None:
        self.data = {}
        self.invalidations: list[tuple] = []
        self.fail_get = False

    async def get_locais(self, team_id, funcionario_id):
        if self.fail_get:
            raise RuntimeError("redis down")
        return self.data.get((team_id, funcionario_id))

    async def set_locais(self, team_id, funcionario_id, locais):
        self.data[(team_id, funcionario_id)] = locais

    async def invalidate(self, team_id, funcionario_id):
        self.invalidations.append((team_id, funcionario_id))
        self.data.pop((team_id, funcionario_id), None)


@pytest.mark.asyncio
async def test_create_local_invalidates_geofence_cache():
    from app.application.services.rh_ponto_service import CreateLocalPontoDTO, RhLocalPontoService

    current_user = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(current_user.team.id)
    cache = _FakeGeofenceCache()
    service = RhLocalPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo(),
        audit_repo=_FakeAuditRepo(),
        geofence_cache=cache,
        uow=_FakeUow(),
    )

    local = await service.create_local(
        funcionario.id,
        CreateLocalPontoDTO(
            nome="Obra Centro",
            latitude=-16.6869,
            longitude=-49.2648,
            raio_metros=100,
        ),
        current_user,
    )

    assert local.nome == "Obra Centro"
    assert cache.invalidations == [(current_user.team.id, funcionario.id)]


@pytest.mark.asyncio
async def test_create_local_validates_radius_bounds_and_default():
    from app.application.services.rh_ponto_service import CreateLocalPontoDTO, RhLocalPontoService

    current_user = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(current_user.team.id)
    service = RhLocalPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo(),
        audit_repo=_FakeAuditRepo(),
        geofence_cache=_FakeGeofenceCache(),
        uow=_FakeUow(),
    )

    local = await service.create_local(
        funcionario.id,
        CreateLocalPontoDTO(nome="Obra Centro", latitude=-16.6869, longitude=-49.2648),
        current_user,
    )

    assert local.raio_metros == 100
    with pytest.raises(DomainError, match="Raio"):
        await service.create_local(
            funcionario.id,
            CreateLocalPontoDTO.model_construct(nome="Muito pequeno", latitude=-16.6869, longitude=-49.2648, raio_metros=10),
            current_user,
        )
    with pytest.raises(DomainError, match="Raio"):
        await service.create_local(
            funcionario.id,
            CreateLocalPontoDTO.model_construct(nome="Muito grande", latitude=-16.6869, longitude=-49.2648, raio_metros=1500),
            current_user,
        )


@pytest.mark.asyncio
async def test_update_and_delete_local_validate_radius_soft_delete_audit_and_cache():
    from app.application.services.rh_ponto_service import CreateLocalPontoDTO, RhLocalPontoService, UpdateLocalPontoDTO

    current_user = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(current_user.team.id)
    local_repo = _FakeLocalPontoRepo()
    audit_repo = _FakeAuditRepo()
    cache = _FakeGeofenceCache()
    service = RhLocalPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=local_repo,
        audit_repo=audit_repo,
        geofence_cache=cache,
        uow=_FakeUow(),
    )
    local = await service.create_local(
        funcionario.id,
        CreateLocalPontoDTO(nome="Obra Centro", latitude=-16.6869, longitude=-49.2648, raio_metros=100),
        current_user,
    )

    with pytest.raises(DomainError, match="Raio"):
        await service.update_local(local.id, UpdateLocalPontoDTO.model_construct(raio_metros=5), current_user)

    updated = await service.update_local(local.id, UpdateLocalPontoDTO(raio_metros=250), current_user)
    await service.delete_local(local.id, current_user)

    assert updated.raio_metros == 250
    assert local_repo.by_id[local.id].is_deleted is True
    assert [event.action for event in audit_repo.events] == [
        "rh.local_ponto.created",
        "rh.local_ponto.updated",
        "rh.local_ponto.deleted",
    ]
    assert cache.invalidations == [
        (current_user.team.id, funcionario.id),
        (current_user.team.id, funcionario.id),
        (current_user.team.id, funcionario.id),
    ]


@pytest.mark.asyncio
async def test_registrar_ponto_without_geofence_creates_validado():
    from app.application.services.rh_ponto_service import RegistrarPontoDTO, RequestContext, RhPontoService

    current_user = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    registro_repo = _FakeRegistroPontoRepo()
    service = RhPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo(),
        registro_ponto_repo=registro_repo,
        audit_repo=_FakeAuditRepo(),
        geofence_cache=_FakeGeofenceCache(),
        idempotency_repo=None,
        uow=_FakeUow(),
    )

    registro = await service.registrar_ponto(
        RegistrarPontoDTO(
            tipo=TipoPonto.ENTRADA,
            latitude=-16.6869,
            longitude=-49.2648,
            client_timestamp=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
            gps_accuracy_meters=12.5,
            device_fingerprint="device-1",
        ),
        current_user,
        RequestContext(
            request_id="req-1",
            ip_hash="iphash",
            user_agent="pytest",
            idempotency_key=None,
        ),
    )

    assert registro.status == StatusPonto.VALIDADO
    assert registro.local_ponto_id is None
    assert registro_repo.items[-1].gps_accuracy_meters == 12.5


@pytest.mark.asyncio
async def test_registrar_ponto_accepts_admin_when_linked_to_funcionario():
    from app.application.services.rh_ponto_service import RegistrarPontoDTO, RequestContext, RhPontoService

    current_user = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    registro_repo = _FakeRegistroPontoRepo()
    service = RhPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo(),
        registro_ponto_repo=registro_repo,
        audit_repo=_FakeAuditRepo(),
        geofence_cache=_FakeGeofenceCache(),
        idempotency_repo=None,
        uow=_FakeUow(),
    )

    registro = await service.registrar_ponto(
        RegistrarPontoDTO(
            tipo=TipoPonto.ENTRADA,
            latitude=-16.6869,
            longitude=-49.2648,
            client_timestamp=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
        ),
        current_user,
        RequestContext(request_id="req-1", ip_hash="iphash", user_agent="pytest", idempotency_key=None),
    )

    assert registro.status == StatusPonto.VALIDADO
    assert registro.funcionario_id == funcionario.id


@pytest.mark.asyncio
async def test_registrar_ponto_outside_geofence_persists_negado_and_raises():
    from app.application.services.rh_ponto_service import RegistrarPontoDTO, RequestContext, RhPontoService

    current_user = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    local = LocalPonto(
        team_id=current_user.team.id,
        funcionario_id=funcionario.id,
        nome="Obra Centro",
        latitude=-16.6869,
        longitude=-49.2648,
        raio_metros=50,
    )
    registro_repo = _FakeRegistroPontoRepo()
    service = RhPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo([local]),
        registro_ponto_repo=registro_repo,
        audit_repo=_FakeAuditRepo(),
        geofence_cache=_FakeGeofenceCache(),
        idempotency_repo=None,
        uow=_FakeUow(),
    )

    with pytest.raises(DomainError):
        await service.registrar_ponto(
            RegistrarPontoDTO(
                tipo=TipoPonto.ENTRADA,
                latitude=-16.7000,
                longitude=-49.3000,
            ),
            current_user,
            RequestContext(
                request_id="req-2",
                ip_hash="iphash",
                user_agent="pytest",
                idempotency_key=None,
            ),
        )

    assert registro_repo.items[-1].status == StatusPonto.NEGADO
    assert registro_repo.items[-1].denial_reason == "outside_geofence"


@pytest.mark.asyncio
async def test_registrar_ponto_marks_inconsistente_for_two_entradas():
    from app.application.services.rh_ponto_service import RegistrarPontoDTO, RequestContext, RhPontoService

    current_user = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    registro_repo = _FakeRegistroPontoRepo(
        [
            RegistroPonto(
                team_id=current_user.team.id,
                funcionario_id=funcionario.id,
                tipo=TipoPonto.ENTRADA,
                timestamp=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
                latitude=-16.6869,
                longitude=-49.2648,
            )
        ]
    )
    service = RhPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo(),
        registro_ponto_repo=registro_repo,
        audit_repo=_FakeAuditRepo(),
        geofence_cache=_FakeGeofenceCache(),
        idempotency_repo=None,
        uow=_FakeUow(),
    )

    registro = await service.registrar_ponto(
        RegistrarPontoDTO(
            tipo=TipoPonto.ENTRADA,
            latitude=-16.6869,
            longitude=-49.2648,
        ),
        current_user,
        RequestContext(
            request_id="req-3",
            ip_hash="iphash",
            user_agent="pytest",
            idempotency_key=None,
        ),
    )

    assert registro.status == StatusPonto.INCONSISTENTE


def test_haversine_distance_returns_short_distance_for_nearby_points():
    from app.application.services.rh_ponto_service import haversine_distance_meters

    distance = haversine_distance_meters(-16.6869, -49.2648, -16.6870, -49.2649)

    assert 0 < distance < 20


@pytest.mark.asyncio
async def test_list_meus_pontos_returns_full_total_not_only_current_page():
    from app.application.services.rh_ponto_service import RhPontoService

    current_user = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    registros = [
        RegistroPonto(
            team_id=current_user.team.id,
            funcionario_id=funcionario.id,
            tipo=TipoPonto.ENTRADA if index % 2 == 0 else TipoPonto.SAIDA,
            timestamp=datetime(2026, 4, 28, 8 + index, 0, tzinfo=timezone.utc),
            latitude=-16.6869,
            longitude=-49.2648,
        )
        for index in range(3)
    ]
    service = RhPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo(),
        registro_ponto_repo=_FakeRegistroPontoRepo(registros),
        audit_repo=_FakeAuditRepo(),
        geofence_cache=_FakeGeofenceCache(),
        idempotency_repo=None,
        uow=_FakeUow(),
    )

    items, total = await service.list_meus_pontos(current_user, page=1, limit=2)

    assert len(items) == 2
    assert total == 3


@pytest.mark.asyncio
async def test_list_meus_pontos_accepts_admin_when_linked_to_funcionario():
    from app.application.services.rh_ponto_service import RhPontoService

    current_user = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    registros = [
        RegistroPonto(
            team_id=current_user.team.id,
            funcionario_id=funcionario.id,
            tipo=TipoPonto.ENTRADA,
            timestamp=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
            latitude=-16.6869,
            longitude=-49.2648,
        )
    ]
    service = RhPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo(),
        registro_ponto_repo=_FakeRegistroPontoRepo(registros),
        audit_repo=_FakeAuditRepo(),
        geofence_cache=_FakeGeofenceCache(),
        idempotency_repo=None,
        uow=_FakeUow(),
    )

    items, total = await service.list_meus_pontos(current_user, page=1, limit=10)

    assert len(items) == 1
    assert total == 1


@pytest.mark.asyncio
async def test_registrar_ponto_rejects_duplicate_idempotency_key():
    from app.application.services.rh_ponto_service import RegistrarPontoDTO, RequestContext, RhPontoService

    current_user = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    service = RhPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo(),
        registro_ponto_repo=_FakeRegistroPontoRepo(),
        audit_repo=_FakeAuditRepo(),
        geofence_cache=_FakeGeofenceCache(),
        idempotency_repo=_FakeIdempotencyRepo(),
        uow=_FakeUow(),
    )
    dto = RegistrarPontoDTO(
        tipo=TipoPonto.ENTRADA,
        latitude=-16.6869,
        longitude=-49.2648,
    )

    await service.registrar_ponto(
        dto,
        current_user,
        RequestContext(idempotency_key="same-key"),
    )

    with pytest.raises(DomainError):
        await service.registrar_ponto(
            dto,
            current_user,
            RequestContext(idempotency_key="same-key"),
        )


@pytest.mark.asyncio
async def test_obter_dia_ponto_enriches_registros_with_local_metadata_and_outside_flag():
    from app.application.services.rh_ponto_service import RhPontoService

    current_user = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(current_user.team.id)
    local = LocalPonto(
        team_id=current_user.team.id,
        funcionario_id=funcionario.id,
        nome="Obra Centro",
        latitude=-16.6869,
        longitude=-49.2648,
        raio_metros=50,
    )
    inside = RegistroPonto(
        team_id=current_user.team.id,
        funcionario_id=funcionario.id,
        tipo=TipoPonto.ENTRADA,
        timestamp=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
        latitude=-16.68691,
        longitude=-49.26481,
        status=StatusPonto.VALIDADO,
        local_ponto_id=local.id,
        gps_accuracy_meters=8.0,
    )
    outside = RegistroPonto(
        team_id=current_user.team.id,
        funcionario_id=funcionario.id,
        tipo=TipoPonto.SAIDA,
        timestamp=datetime(2026, 4, 28, 18, 0, tzinfo=timezone.utc),
        latitude=-16.7000,
        longitude=-49.3000,
        status=StatusPonto.NEGADO,
        denial_reason="outside_geofence",
        gps_accuracy_meters=12.0,
    )
    service = RhPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo([local]),
        registro_ponto_repo=_FakeRegistroPontoRepo([inside, outside]),
        audit_repo=_FakeAuditRepo(),
        geofence_cache=_FakeGeofenceCache(),
        idempotency_repo=None,
        uow=_FakeUow(),
    )

    detail = await service.obter_dia_ponto(current_user, funcionario.id, datetime(2026, 4, 28).date())

    assert detail["status"] == "com_negacao"
    assert detail["local_autorizado_nome"] == "Obra Centro"
    assert detail["registros"][0].local_ponto_nome == "Obra Centro"
    assert detail["registros"][0].fora_local_autorizado is False
    assert detail["registros"][0].latitude == -16.68691
    assert detail["registros"][0].longitude == -49.26481
    assert detail["registros"][0].gps_accuracy_meters == 8.0
    assert detail["registros"][1].local_ponto_nome is None
    assert detail["registros"][1].fora_local_autorizado is True
