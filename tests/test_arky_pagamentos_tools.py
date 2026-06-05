"""Testes unitarios das tools do Arky para pagamentos agendados.

Foco: minimizacao de dados sensiveis (Pix nunca exposto), validacao de entrada
e o padrao prepare->preview (nada e criado direto pela tool).
"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.application.services.arky.tools import financeiro as fin_tools
from app.application.services.arky.tools import diaristas as diarista_tools
from app.application.services.arky.tools.context import ArkyToolContext
from app.domain.entities.financeiro import MovClass, PagamentoAgendado, PaymentStatus
from app.domain.entities.money import Money
from app.domain.entities.user import Roles
from app.domain.errors import DomainError


def _user(team_id, role=Roles.FINANCEIRO):
    return SimpleNamespace(id=uuid4(), nome="User", role=role,
                           team=SimpleNamespace(id=team_id))


def _pagamento(team_id, title="Diaria Pedro", status=PaymentStatus.AGUARDANDO,
               data_agendada=None, payment_cod="pix-SECRETO", payment_date=None):
    p = object.__new__(PagamentoAgendado)
    p.id = uuid4()
    p.team_id = team_id
    p.title = title
    p.details = "detalhe"
    p.valor = Money(Decimal("200.00"))
    p.classe = MovClass.DIARISTA
    p.data_agendada = data_agendada or datetime.now(timezone.utc)
    p.payment_cod = payment_cod
    p.pix_copy_and_past = "00020126_PIX_COMPLETO_SECRETO"
    p.status = status
    p.payment_date = payment_date
    p.obra_id = None
    p.diarist_id = None
    p.created_by_user_id = None
    p.created_by_role = None
    p.created_by_name = "Maria Fin"
    p.created_by_engineer = False
    p.created_at = datetime.now(timezone.utc)
    return p


def _ctx(team_id, role=Roles.FINANCEIRO, *, financeiro_service=None,
         diarist_service=None, obra_service=None, preview_repo=None):
    return ArkyToolContext(
        user=_user(team_id, role),
        team_id=team_id,
        obra_service=obra_service,
        financeiro_service=financeiro_service,
        diarist_service=diarist_service,
        arky_preview_repo=preview_repo,
        uow=AsyncMock(),
    )


# ── overview ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_overview_returns_overdue_without_pix(team_id):
    vencido = _pagamento(team_id, data_agendada=datetime.now(timezone.utc) - timedelta(days=3))
    fin = SimpleNamespace(list_pagamentos_overdue=AsyncMock(return_value=[vencido]))
    ctx = _ctx(team_id, financeiro_service=fin)

    out = await fin_tools.financeiro_pagamentos_overview({}, ctx)

    assert out["total_atrasados"] == 1
    assert out["valor_total_atrasado"] == 200.0
    item = out["atrasados"][0]
    assert item["dias_em_atraso"] >= 3
    assert item["tem_codigo_pagamento"] is True
    # Pix e codigo do recebedor NUNCA aparecem
    blob = str(out)
    assert "SECRETO" not in blob
    assert "payment_cod" not in item
    assert "pix_copy_and_past" not in item


@pytest.mark.asyncio
async def test_overview_handles_service_error(team_id):
    fin = SimpleNamespace(list_pagamentos_overdue=AsyncMock(side_effect=RuntimeError("boom")))
    ctx = _ctx(team_id, financeiro_service=fin)
    out = await fin_tools.financeiro_pagamentos_overview({}, ctx)
    assert "error" in out


# ── buscar ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buscar_rejects_short_query(team_id):
    ctx = _ctx(team_id, financeiro_service=SimpleNamespace())
    out = await fin_tools.financeiro_buscar_pagamentos({"query": "a"}, ctx)
    assert "error" in out


@pytest.mark.asyncio
async def test_buscar_identifies_last_paid_and_hides_pix(team_id):
    pago = _pagamento(team_id, status=PaymentStatus.PAGO,
                      payment_date=datetime.now(timezone.utc))
    aguardando = _pagamento(team_id, status=PaymentStatus.AGUARDANDO)
    fin = SimpleNamespace(search_pagamentos=AsyncMock(return_value=[pago, aguardando]))
    ctx = _ctx(team_id, financeiro_service=fin)

    out = await fin_tools.financeiro_buscar_pagamentos({"query": "pedro"}, ctx)

    assert out["total"] == 2
    assert out["ultimo_pagamento_efetuado"]["status"] == "pago"
    assert "SECRETO" not in str(out)


# ── prepare (lista) ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prepare_rejects_empty_list(team_id):
    ctx = _ctx(team_id, preview_repo=AsyncMock())
    out = await fin_tools.financeiro_prepare_pagamentos({"pagamentos": []}, ctx)
    assert "error" in out


@pytest.mark.asyncio
async def test_prepare_rejects_invalid_classe(team_id):
    ctx = _ctx(team_id, preview_repo=AsyncMock())
    out = await fin_tools.financeiro_prepare_pagamentos(
        {"pagamentos": [{"title": "x", "valor": 10, "classe": "inexistente"}]}, ctx
    )
    assert "error" in out and "classe" in out["error"]


@pytest.mark.asyncio
async def test_prepare_engineer_requires_payment_code(team_id):
    ctx = _ctx(team_id, role=Roles.ENGENHEIRO, preview_repo=AsyncMock())
    out = await fin_tools.financeiro_prepare_pagamentos(
        {"pagamentos": [{"title": "Diaria", "valor": 200, "classe": "diarista"}]}, ctx
    )
    assert "error" in out and "engenheiro" in out["error"].lower()


@pytest.mark.asyncio
async def test_prepare_saves_single_preview_for_list(team_id):
    preview_repo = AsyncMock()
    preview_repo.save = AsyncMock(side_effect=lambda p: SimpleNamespace(
        id=uuid4(), summary=p.summary, risk_level=p.risk_level))
    ctx = _ctx(team_id, role=Roles.FINANCEIRO, preview_repo=preview_repo)

    out = await fin_tools.financeiro_prepare_pagamentos(
        {"pagamentos": [
            {"title": "Material obra X", "valor": 120, "classe": "material", "payment_cod": "pix-1"},
            {"title": "Diaria Pedro", "valor": 200, "classe": "diarista"},
        ]}, ctx
    )

    assert out["action_type"] == "prepare_create_pagamentos"
    assert out["requires_confirmation"] is True
    assert out["preview"]["quantidade"] == 2
    assert out["preview"]["total"] == 320.0
    preview_repo.save.assert_awaited_once()
    # A prévia exibida ao usuario nao contem o codigo Pix em texto, so o booleano
    item = out["preview"]["itens"][0]
    assert item["tem_codigo_pagamento"] is True
    assert "payment_cod" not in item


@pytest.mark.asyncio
async def test_prepare_resolves_obra_and_diarist(team_id):
    preview_repo = AsyncMock()
    preview_repo.save = AsyncMock(side_effect=lambda p: SimpleNamespace(
        id=uuid4(), summary=p.summary, risk_level=p.risk_level))
    obra_id, diarist_id = uuid4(), uuid4()
    obra_service = SimpleNamespace(get_obra=AsyncMock(
        return_value=SimpleNamespace(title="OSP.150")))
    diarist_service = SimpleNamespace(get_diarist=AsyncMock(
        return_value=SimpleNamespace(nome="Luciene")))
    ctx = _ctx(team_id, preview_repo=preview_repo,
               obra_service=obra_service, diarist_service=diarist_service)

    out = await fin_tools.financeiro_prepare_pagamentos(
        {"pagamentos": [{
            "title": "Diaria Luciene", "valor": 180, "classe": "diarista",
            "payment_cod": "pix-1", "obra_id": str(obra_id), "diarist_id": str(diarist_id),
        }]}, ctx
    )
    item = out["preview"]["itens"][0]
    assert item["obra_title"] == "OSP.150"
    assert item["diarist_nome"] == "Luciene"


@pytest.mark.asyncio
async def test_prepare_rejects_unknown_obra(team_id):
    preview_repo = AsyncMock()
    obra_service = SimpleNamespace(get_obra=AsyncMock(side_effect=DomainError("nao encontrada")))
    ctx = _ctx(team_id, preview_repo=preview_repo, obra_service=obra_service)
    out = await fin_tools.financeiro_prepare_pagamentos(
        {"pagamentos": [{
            "title": "x", "valor": 10, "classe": "material",
            "payment_cod": "pix", "obra_id": str(uuid4()),
        }]}, ctx
    )
    assert "error" in out and "Obra" in out["error"]


# ── diaristas_list ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_diaristas_list_omits_chave_pix(team_id):
    diarist = SimpleNamespace(id=uuid4(), nome="Luciene",
                              valor_diaria=Decimal("150.00"), chave_pix="pix-SECRETO")
    diarist_service = SimpleNamespace(list_diarists=AsyncMock(return_value=[diarist]))
    ctx = _ctx(team_id, diarist_service=diarist_service)

    out = await diarista_tools.diaristas_list({}, ctx)

    assert out["total"] == 1
    d = out["diaristas"][0]
    assert d["nome"] == "Luciene"
    assert d["valor_diaria"] == 150.0
    assert "chave_pix" not in d
    assert "SECRETO" not in str(out)
