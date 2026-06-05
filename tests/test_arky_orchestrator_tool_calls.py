"""Regression tests for tool-call continuity in Arky tool loops (OpenRouter).

Replaces the former Gemini thought-signature test: with the provider-agnostic
layer, multi-round function calling is stitched together via `tool_call_id`
(OpenAI/OpenRouter contract), not via thought signatures.
"""

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
from app.infra.ai.llm import LLMResponse, ToolCall


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


class _FakeLLM:
    def __init__(self):
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="call_abc",
                        name="obras_prepare_create",
                        args={"title": "Teste"},
                    )
                ],
                model_used="google/gemma-4-31b-it:free",
            )
        return LLMResponse(
            text='{"message": "ok", "intent": "general", "cards": [], "actions": [], "citations": []}',
            model_used="google/gemma-4-31b-it:free",
        )


@pytest.mark.asyncio
async def test_orchestrator_links_tool_result_to_call_id_in_next_round():
    user = _make_user()
    llm = _FakeLLM()

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
        role="strong",
        chain=["google/gemini-3.5-flash", "google/gemma-4-31b-it:free"],
        reason="test",
    )

    uow = MagicMock()
    uow.commit = AsyncMock()

    orchestrator = ArkyOrchestrator(
        llm_client=llm,
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

    # The whole fallback chain must be forwarded to the client.
    assert llm.calls[0]["models"] == [
        "google/gemini-3.5-flash",
        "google/gemma-4-31b-it:free",
    ]

    second_round_messages = llm.calls[1]["messages"]

    # The assistant tool-call request is echoed back with the same call id.
    assistant_call = next(
        m for m in second_round_messages
        if m["role"] == "assistant" and m.get("tool_calls")
    )
    assert assistant_call["tool_calls"][0]["id"] == "call_abc"
    assert assistant_call["tool_calls"][0]["function"]["name"] == "obras_prepare_create"

    # The tool result references that same call id.
    tool_result = next(m for m in second_round_messages if m["role"] == "tool")
    assert tool_result["tool_call_id"] == "call_abc"
    assert tool_result["name"] == "obras_prepare_create"
