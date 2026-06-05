"""E2E (integracao) do fluxo de pagamentos agendados via Arky.

Exercita o caminho completo com componentes reais (policy, registry, context,
orchestrator, FinanceiroService) e fakes apenas nas bordas de IO (LLM, repos):

  chat -> modelo chama financeiro_prepare_pagamentos -> preview salva
       -> confirm executa create_pagamentos com autoria do usuario autenticado.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.application.services.arky.context_builder import ArkyContextBuilder
from app.application.services.arky.model_router import ArkyModelRouter
from app.application.services.arky.orchestrator import ArkyChatInput, ArkyOrchestrator
from app.application.services.arky.policies import ArkyPolicyEngine
from app.application.services.arky.tool_registry import ArkyToolRegistry
from app.application.services.financeiro_service import FinanceiroService
from app.domain.entities.arky import ArkyActionPreview
from app.domain.entities.team import Plans, Team
from app.domain.entities.user import Roles, User
from app.infra.ai.llm import LLMResponse, ToolCall


def _make_user(role=Roles.FINANCEIRO) -> User:
    team = object.__new__(Team)
    team.id = uuid4()
    team.title = "T"
    team.cnpj = "12345678000195"
    team.plan = Plans.PRO
    team.expiration_date = datetime.now(timezone.utc)

    user = object.__new__(User)
    user.id = uuid4()
    user.nome = "Maria Fin"
    user.email = "maria@example.com"
    user.senha_hash = "h"
    user.role = role
    user.team = team
    user.cpf = None
    return user


class _InMemoryPreviewRepo:
    def __init__(self):
        self.store: dict = {}

    async def save(self, preview: ArkyActionPreview):
        self.store[preview.id] = preview
        return preview

    async def get_by_id(self, pid, team_id, user_id=None):
        p = self.store.get(pid)
        if not p or p.team_id != team_id:
            return None
        return p

    async def update(self, preview):
        self.store[preview.id] = preview
        return preview


class _PrepareThenFinishLLM:
    """Round 1: pede a tool de preparar pagamentos. Round 2: resposta final."""

    def __init__(self, pagamentos_args):
        self._args = pagamentos_args
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return LLMResponse(
                text="",
                tool_calls=[ToolCall(id="call_1", name="financeiro_prepare_pagamentos",
                                     args={"pagamentos": self._args})],
                model_used="google/gemma-4-31b-it:free",
            )
        return LLMResponse(
            text='{"message": "Aqui esta a sugestao", "intent": "create_pagamentos",'
                 ' "cards": [], "actions": [], "citations": []}',
            model_used="google/gemma-4-31b-it:free",
        )


def _build_orchestrator(user, llm, preview_repo, pag_repo):
    diarist_repo = AsyncMock()
    diarist_repo.get_by_id = AsyncMock(side_effect=__import__(
        "app.domain.errors", fromlist=["DomainError"]).DomainError("x"))
    financeiro_service = FinanceiroService(
        mov_repo=AsyncMock(), pagamento_repo=pag_repo,
        mov_attachment_repo=AsyncMock(), diarist_repo=diarist_repo,
        uow=AsyncMock(),
    )

    conv_repo = MagicMock()
    conv_repo.save = AsyncMock(side_effect=lambda c: c)
    conv_repo.get_by_id = AsyncMock(return_value=None)
    msg_repo = MagicMock()
    msg_repo.save = AsyncMock(side_effect=lambda m: m)
    msg_repo.list_by_conversation = AsyncMock(return_value=[
        SimpleNamespace(role="user", content="cadastrar pagamentos")
    ])
    uow = MagicMock()
    uow.commit = AsyncMock()

    return ArkyOrchestrator(
        llm_client=llm,
        context_builder=ArkyContextBuilder(),
        model_router=ArkyModelRouter(),
        policy_engine=ArkyPolicyEngine(),
        tool_registry=ArkyToolRegistry(),
        audit_service=MagicMock(record=AsyncMock()),
        conv_repo=conv_repo,
        msg_repo=msg_repo,
        preview_repo=preview_repo,
        uow=uow,
        financeiro_service=financeiro_service,
    )


@pytest.mark.asyncio
async def test_full_flow_prepare_then_confirm_creates_payments():
    user = _make_user(Roles.FINANCEIRO)
    pag_repo = AsyncMock()
    pag_repo.save = AsyncMock(side_effect=lambda p: p)
    preview_repo = _InMemoryPreviewRepo()

    llm = _PrepareThenFinishLLM([
        {"title": "Material para obra X", "valor": 120, "classe": "material", "payment_cod": "pix-XXXX"},
        {"title": "Diaria Luciene OSP.150", "valor": 180, "classe": "diarista", "payment_cod": "pix-YYYY"},
    ])
    orch = _build_orchestrator(user, llm, preview_repo, pag_repo)

    # --- 1) chat: o modelo prepara a sugestao (nada criado ainda) ---
    out = await orch.chat(ArkyChatInput(
        message="Arky, cadastra 2 pagamentos pra hoje",
        user=user, team_id=user.team.id,
    ))
    assert "sugestao" in out.message.lower()
    pag_repo.save.assert_not_awaited()  # prepare NAO cria

    assert len(preview_repo.store) == 1
    preview = next(iter(preview_repo.store.values()))
    assert preview.action_type == "prepare_create_pagamentos"
    assert len(preview.payload["itens"]) == 2

    # Free-first: tarefa de extracao usou a cadeia gratuita liderada por Gemma 4.
    assert llm.calls[0]["models"][0] == "google/gemma-4-31b-it:free"

    # --- 2) confirm: executa a criacao real com autoria do usuario ---
    preview.confirm()
    result = await orch.execute_confirmed_action(preview, user)

    assert result["created"] == 2
    assert result["total"] == 300.0
    assert pag_repo.save.await_count == 2


@pytest.mark.asyncio
async def test_confirm_other_action_type_is_noop():
    user = _make_user(Roles.ADMIN)
    orch = _build_orchestrator(user, _PrepareThenFinishLLM([]), _InMemoryPreviewRepo(), AsyncMock())
    preview = ArkyActionPreview(
        team_id=user.team.id, user_id=user.id, conversation_id=uuid4(),
        action_type="prepare_create_obra", payload={"title": "x"},
        summary="Criar obra", risk_level="preparacao",
    )
    # Acoes preview-only nao executam nada (retrocompatibilidade).
    assert await orch.execute_confirmed_action(preview, user) is None


@pytest.mark.asyncio
async def test_confirm_rejects_cross_tenant_payload():
    user = _make_user(Roles.FINANCEIRO)
    orch = _build_orchestrator(user, _PrepareThenFinishLLM([]), _InMemoryPreviewRepo(), AsyncMock())
    preview = ArkyActionPreview(
        team_id=user.team.id, user_id=user.id, conversation_id=uuid4(),
        action_type="prepare_create_pagamentos",
        payload={"team_id": str(uuid4()), "itens": [{"title": "x", "valor": "1",
                 "classe": "material", "data_agendada": datetime.now(timezone.utc).isoformat()}]},
        summary="x", risk_level="preparacao",
    )
    from app.domain.errors import DomainError
    with pytest.raises(DomainError, match="tenant"):
        await orch.execute_confirmed_action(preview, user)
