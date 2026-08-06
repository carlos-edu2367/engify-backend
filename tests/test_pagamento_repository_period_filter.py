"""Filtro de pagamentos por período de vencimento (data_agendada).

Testes unitários puros: compilam o statement e inspecionam o SQL, sem DB.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.application.dtos.financeiro import PagamentoFiltersDTO
from app.domain.entities.financeiro import PaymentStatus
from app.infra.db.repositories.financeiro_repository import PagamentoAgendadoRepositoryImpl


class _FakeScalars:
    def all(self):
        return []


class _FakeResult:
    def scalars(self):
        return _FakeScalars()

    def scalar_one(self):
        return 0


class _RecordingSession:
    """Captura o último statement executado para inspecionar o SQL compilado."""

    def __init__(self):
        self.last_statement = None

    async def execute(self, stmt):
        self.last_statement = stmt
        return _FakeResult()


def _compiled(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _month_filters(status: PaymentStatus | None = None) -> PagamentoFiltersDTO:
    """Recorte de um mês cheio, como o front monta ao escolher 2026-03."""
    return PagamentoFiltersDTO(
        status=status,
        period_start=datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
        period_end=datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["list", "count"])
async def test_period_filter_limita_por_data_agendada(method):
    session = _RecordingSession()
    repo = PagamentoAgendadoRepositoryImpl(session)
    team_id = uuid4()
    filters = _month_filters()

    if method == "list":
        await repo.list_by_team(team_id, page=1, limit=50, filters=filters)
    else:
        await repo.count_by_team(team_id, filters=filters)

    sql = _compiled(session.last_statement)
    assert "data_agendada >=" in sql
    assert "data_agendada <=" in sql
    assert "2026-03-01" in sql
    assert "2026-03-31" in sql


@pytest.mark.asyncio
async def test_period_filter_combina_com_status():
    session = _RecordingSession()
    repo = PagamentoAgendadoRepositoryImpl(session)

    await repo.list_by_team(
        uuid4(), page=1, limit=50, filters=_month_filters(status=PaymentStatus.AGUARDANDO)
    )

    sql = _compiled(session.last_statement)
    assert "data_agendada >=" in sql
    assert "data_agendada <=" in sql
    assert PaymentStatus.AGUARDANDO.value in sql


@pytest.mark.asyncio
async def test_apenas_period_start_nao_gera_limite_superior():
    session = _RecordingSession()
    repo = PagamentoAgendadoRepositoryImpl(session)

    await repo.list_by_team(
        uuid4(), page=1, limit=50,
        filters=PagamentoFiltersDTO(period_start=datetime(2026, 3, 1, tzinfo=timezone.utc)),
    )

    sql = _compiled(session.last_statement)
    assert "data_agendada >=" in sql
    assert "data_agendada <=" not in sql


@pytest.mark.asyncio
async def test_dependency_repassa_period_para_o_dto():
    """Garante a fiação query param -> DTO usada pelo GET /financeiro/pagamentos."""
    from app.http.dependencies.financeiro_filters import get_pagamento_filters

    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end = datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc)
    filters = await get_pagamento_filters(
        status=None, obra_id=None, period_start=start, period_end=end
    )

    assert filters.period_start == start
    assert filters.period_end == end


@pytest.mark.asyncio
async def test_sem_period_nao_filtra_por_data():
    session = _RecordingSession()
    repo = PagamentoAgendadoRepositoryImpl(session)

    await repo.list_by_team(uuid4(), page=1, limit=50, filters=PagamentoFiltersDTO())

    sql = _compiled(session.last_statement)
    assert "data_agendada >=" not in sql
    assert "data_agendada <=" not in sql


@pytest.mark.asyncio
async def test_filtro_comprovante_pendente_gera_clausulas_esperadas():
    session = _RecordingSession()
    repo = PagamentoAgendadoRepositoryImpl(session)

    await repo.list_by_team(
        uuid4(), page=1, limit=50,
        filters=PagamentoFiltersDTO(comprovante_pendente=True),
    )

    sql = _compiled(session.last_statement)
    assert "WHERE" in sql
    where_clause = sql.split("WHERE", 1)[1]
    assert "requires_receipt" in where_clause
    assert "receipt_attached" in where_clause
    assert PaymentStatus.PAGO.value in where_clause


@pytest.mark.asyncio
async def test_filtro_comprovante_pendente_false_nao_filtra():
    session = _RecordingSession()
    repo = PagamentoAgendadoRepositoryImpl(session)

    await repo.list_by_team(
        uuid4(), page=1, limit=50,
        filters=PagamentoFiltersDTO(comprovante_pendente=False),
    )

    sql = _compiled(session.last_statement)
    where_clause = sql.split("WHERE", 1)[1] if "WHERE" in sql else ""
    assert "requires_receipt" not in where_clause
    assert "receipt_attached" not in where_clause
