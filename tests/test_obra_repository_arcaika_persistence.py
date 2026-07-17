"""Testes de round-trip real (Postgres) de ObraRepositoryImpl.save() para os
campos de rastreabilidade Arcaika (origem/arcaika_orcamento_id/
arcaika_solicitacao_id).

Bug de produção (2026-07-17): `unlink_obra`/`link_existing_obra`
(IntegracaoArcaikaService) atualizam esses campos no objeto de domínio e
chamam `obra_repo.save(obra)` seguido de `uow.commit()` sem erro — mas
`ObraModel.update_from_domain` nunca copiava esses três campos de volta para
a linha no banco (só `from_domain`, usado na criação, os define). O commit
"funciona" e nada é persistido. Só um teste que recarrega do banco (não um
fake que apenas registra o objeto em memória) pega isso.

Requer um Postgres real acessível via DATABASE_URL. Cada teste roda dentro de
uma transação com rollback ao final.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.domain.entities.obra import Obra, ObraOrigem
from app.infra.db.models.team_model import TeamModel
from app.infra.db.repositories.obra_repository import ObraRepositoryImpl

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:55432/engify"
)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            if trans.is_active:
                await trans.rollback()
    await engine.dispose()


async def _make_team(session: AsyncSession) -> TeamModel:
    team = TeamModel(
        id=uuid.uuid4(),
        title="Time de teste",
        cnpj=uuid.uuid4().hex[:14],
        plan="trial",
        expiration_date=datetime.now(timezone.utc) + timedelta(days=30),
    )
    session.add(team)
    await session.flush()
    return team


def _obra_manual(team_id: uuid.UUID) -> Obra:
    return Obra(
        title="Obra manual", team_id=team_id, responsavel_id=None,
        description="", valor=None, data_entrega=None, categoria_id=None,
    )


@pytest.mark.asyncio
async def test_save_persists_arcaika_link_on_existing_obra(db_session):
    """Reproduz link_existing_obra: uma obra MANUAL já existente é vinculada
    a um orçamento. A mudança precisa sobreviver a um reload do banco."""
    team = await _make_team(db_session)
    repo = ObraRepositoryImpl(db_session)

    obra = await repo.save(_obra_manual(team.id))
    await db_session.flush()
    assert obra.arcaika_orcamento_id is None

    orcamento_id = uuid.uuid4()
    solicitacao_id = uuid.uuid4()
    fetched = await repo.get_by_id(obra.id, team.id)
    fetched.arcaika_orcamento_id = orcamento_id
    fetched.arcaika_solicitacao_id = solicitacao_id
    fetched.origem = ObraOrigem.ARCAIKA
    await repo.save(fetched)

    reloaded = await repo.get_by_id(obra.id, team.id)
    assert reloaded.arcaika_orcamento_id == orcamento_id
    assert reloaded.arcaika_solicitacao_id == solicitacao_id
    assert reloaded.origem == ObraOrigem.ARCAIKA


@pytest.mark.asyncio
async def test_save_persists_arcaika_unlink_on_existing_obra(db_session):
    """Reproduz unlink_obra: uma obra vinculada é desvinculada. A mudança
    precisa sobreviver a um reload do banco (não só existir em memória)."""
    team = await _make_team(db_session)
    repo = ObraRepositoryImpl(db_session)

    orcamento_id = uuid.uuid4()
    obra = Obra(
        title="Obra vinculada por engano", team_id=team.id, responsavel_id=None,
        description="", valor=None, data_entrega=None, categoria_id=None,
        origem=ObraOrigem.ARCAIKA, arcaika_orcamento_id=orcamento_id,
        arcaika_solicitacao_id=uuid.uuid4(),
    )
    saved = await repo.save(obra)
    await db_session.flush()
    assert saved.arcaika_orcamento_id == orcamento_id

    fetched = await repo.get_by_id(saved.id, team.id)
    fetched.arcaika_orcamento_id = None
    fetched.arcaika_solicitacao_id = None
    fetched.origem = ObraOrigem.MANUAL
    await repo.save(fetched)

    reloaded = await repo.get_by_id(saved.id, team.id)
    assert reloaded.arcaika_orcamento_id is None
    assert reloaded.arcaika_solicitacao_id is None
    assert reloaded.origem == ObraOrigem.MANUAL


@pytest.mark.asyncio
async def test_unlink_then_link_different_obra_via_repository(db_session):
    """Reprodução direta do bug de producao: desvincular a obra errada e
    vincular a orçamento_id a uma obra diferente não deve colidir no índice
    único (uq_obras_arcaika_orcamento) — só colide se o unlink anterior não
    tiver persistido de verdade."""
    team = await _make_team(db_session)
    repo = ObraRepositoryImpl(db_session)

    orcamento_id = uuid.uuid4()
    obra_errada = Obra(
        title="Obra errada", team_id=team.id, responsavel_id=None,
        description="", valor=None, data_entrega=None, categoria_id=None,
        origem=ObraOrigem.ARCAIKA, arcaika_orcamento_id=orcamento_id,
        arcaika_solicitacao_id=uuid.uuid4(),
    )
    obra_errada = await repo.save(obra_errada)
    obra_certa = await repo.save(_obra_manual(team.id))
    await db_session.flush()

    # Desvincula a errada.
    fetched_errada = await repo.get_by_id(obra_errada.id, team.id)
    fetched_errada.arcaika_orcamento_id = None
    fetched_errada.arcaika_solicitacao_id = None
    fetched_errada.origem = ObraOrigem.MANUAL
    await repo.save(fetched_errada)
    await db_session.flush()

    # Vincula a certa ao MESMO orcamento_id — não deve colidir.
    fetched_certa = await repo.get_by_id(obra_certa.id, team.id)
    fetched_certa.arcaika_orcamento_id = orcamento_id
    fetched_certa.arcaika_solicitacao_id = uuid.uuid4()
    fetched_certa.origem = ObraOrigem.ARCAIKA
    await repo.save(fetched_certa)
    await db_session.flush()

    reloaded = await repo.get_by_id(obra_certa.id, team.id)
    assert reloaded.arcaika_orcamento_id == orcamento_id
