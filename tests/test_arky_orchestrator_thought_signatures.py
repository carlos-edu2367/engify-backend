"""Regression tests for Gemini thought signatures in Arky tool loops."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.services.arky.context_builder import ArkyContextBuilder
from app.application.services.arky.model_router import ModelSelection
from app.application.services.arky.orchestrator import ArkyChatInput, ArkyOrchestrator
from app.domain.entities.team import Plans, Team
from app.domain.entities.user import Roles, User
from app.infra.ai.gemini_client import GeminiResponse


def _make_user() -> User:
    team = object.__new__(Team)
    team.id = uuid4()
    team.title = "Test Team"
    team.cnpj = "12345678000195"
    team.plan = Plans.PRO
    team.expiration_date = datetime.now(timezone.utc)

    user = object.__new__(User)
    user.id = uuid4()
    user.nome = "Test User"
    user.email = "test@example.com"
    user.senha_hash = "hash"
    user.role = Roles.ADMIN
    user.team = team
    user.cpf = None
    return user


class _FakeGemini:
    def __init__(self):
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return GeminiResponse(
                text="",
                function_calls=[
                    {
                        "name": "obras_prepare_create",
                        "args": {"title": "Teste"},
                        "thought_signature": b"signature-a",
                    }
                ],
            )
        return GeminiResponse(
            text='{"message": "ok", "intent": "general", "cards": [], "actions": [], "citations": []}'
        )


@pytest.mark.asyncio
async def test_orchestrator_returns_function_call_thought_signature_to_next_round():
    user = _make_user()
    gemini = _FakeGemini()

    conv_repo = MagicMock()
    conv_repo.save = AsyncMock(side_effect=lambda conv: conv)

    msg_repo = MagicMock()
    msg_repo.save = AsyncMock(side_effect=lambda msg: msg)
    msg_repo.list_by_conversation = AsyncMock(return_value=[
        SimpleNamespace(role="user", content="crie uma obra")
    ])

    policy = MagicMock()
    policy.get_allowed_tools.return_value = []
    policy.is_tool_allowed.return_value = False

    model_router = MagicMock()
    model_router.select.return_value = ModelSelection(
        model_id="gemini-3.5-flash",
        family="gemini",
        reason="test",
    )

    uow = MagicMock()
    uow.commit = AsyncMock()

    orchestrator = ArkyOrchestrator(
        gemini_client=gemini,
        context_builder=ArkyContextBuilder(),
        model_router=model_router,
        policy_engine=policy,
        tool_registry=MagicMock(),
        audit_service=MagicMock(record=AsyncMock()),
        conv_repo=conv_repo,
        msg_repo=msg_repo,
        preview_repo=MagicMock(),
        uow=uow,
    )

    await orchestrator.chat(
        ArkyChatInput(
            message="crie uma obra",
            user=user,
            team_id=user.team.id,
            screen_data={"module": "obras", "route": "/obras", "path": "/obras"},
        )
    )

    second_round_contents = gemini.calls[1]["contents"]
    model_function_call = next(
        content for content in second_round_contents
        if content["role"] == "model"
    )

    assert model_function_call["parts"][0]["functionCall"]["name"] == "obras_prepare_create"
    assert model_function_call["parts"][0]["thoughtSignature"] == b"signature-a"
