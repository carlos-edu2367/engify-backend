"""
HTTP integration tests for the Arky router.
Uses FastAPI TestClient with mocked dependencies — no real DB or Gemini calls.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.entities.arky import ArkyActionPreview
from app.domain.entities.team import Plans, Team
from app.domain.entities.user import Roles, User
from app.http.dependencies.auth import get_current_user
from app.http.dependencies.services import get_arky_copilot
from app.http.routers.arky import router
from app.application.services.arky.orchestrator import ArkyStreamEvent


def _make_team(team_id=None) -> Team:
    team = object.__new__(Team)
    team.id = team_id or uuid4()
    team.title = "Test Team"
    team.cnpj = "12345678000195"
    team.plan = Plans.PRO
    team.expiration_date = datetime.now(timezone.utc)
    return team


def _make_user(role: Roles = Roles.ADMIN, team_id=None) -> User:
    user = object.__new__(User)
    user.id = uuid4()
    user.nome = "Test User"
    user.email = "test@example.com"
    user.senha_hash = "hash"
    user.role = role
    user.team = _make_team(team_id)
    user.cpf = None
    return user


def _make_chat_output():
    from app.application.services.arky.orchestrator import ArkyChatOutput
    return ArkyChatOutput(
        conversation_id=str(uuid4()),
        message_id=str(uuid4()),
        message="Olá! Como posso ajudar?",
        intent="general",
        cards=[],
        actions=[],
        citations=[],
    )


def _build_app(user: User, copilot_mock=None):
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_current_user] = lambda: user

    if copilot_mock is not None:
        app.dependency_overrides[get_arky_copilot] = lambda: copilot_mock
    else:
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=_make_chat_output())
        app.dependency_overrides[get_arky_copilot] = lambda: mock

    return app


class TestChatEndpoint:
    def test_authenticated_user_can_chat(self):
        user = _make_user()
        app = _build_app(user)
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.post("/arky/chat", json={"message": "olá Arky"})
        assert resp.status_code == 200

        data = resp.json()
        assert "conversation_id" in data
        assert "message" in data
        assert data["message"] == "Olá! Como posso ajudar?"

    def test_chat_response_has_all_fields(self):
        user = _make_user()
        app = _build_app(user)
        client = TestClient(app)

        resp = client.post("/arky/chat", json={"message": "teste"})
        assert resp.status_code == 200

        data = resp.json()
        assert "conversation_id" in data
        assert "message_id" in data
        assert "message" in data
        assert "intent" in data
        assert "cards" in data
        assert "actions" in data
        assert "citations" in data

    def test_empty_message_rejected(self):
        user = _make_user()
        app = _build_app(user)
        client = TestClient(app)

        resp = client.post("/arky/chat", json={"message": ""})
        assert resp.status_code == 422

    def test_missing_message_rejected(self):
        user = _make_user()
        app = _build_app(user)
        client = TestClient(app)

        resp = client.post("/arky/chat", json={})
        assert resp.status_code == 422

    def test_message_too_long_rejected(self):
        user = _make_user()
        app = _build_app(user)
        client = TestClient(app)

        resp = client.post("/arky/chat", json={"message": "x" * 2001})
        assert resp.status_code == 422

    def test_invalid_conversation_id_rejected(self):
        user = _make_user()
        app = _build_app(user)
        client = TestClient(app)

        resp = client.post("/arky/chat", json={"message": "oi", "conversation_id": "not-a-uuid"})
        # invalid UUID format is caught by the router
        assert resp.status_code == 400

    def test_chat_uses_user_team_id_from_jwt(self):
        """team_id must come from the JWT user object, not from any payload field."""
        team_id = uuid4()
        user = _make_user(team_id=team_id)

        captured_inputs = []

        async def mock_chat(inp):
            captured_inputs.append(inp)
            return _make_chat_output()

        mock_copilot = MagicMock()
        mock_copilot.chat = mock_chat

        app = _build_app(user, copilot_mock=mock_copilot)
        client = TestClient(app)

        resp = client.post("/arky/chat", json={"message": "teste"})
        assert resp.status_code == 200

        assert len(captured_inputs) == 1
        inp = captured_inputs[0]
        # team_id must be from JWT user, not from any payload
        assert inp.team_id == team_id
        assert inp.user == user

    def test_screen_context_forwarded(self):
        """Screen context from frontend is forwarded to the orchestrator."""
        user = _make_user()
        captured_inputs = []

        async def mock_chat(inp):
            captured_inputs.append(inp)
            return _make_chat_output()

        mock_copilot = MagicMock()
        mock_copilot.chat = mock_chat

        app = _build_app(user, copilot_mock=mock_copilot)
        client = TestClient(app)

        resp = client.post("/arky/chat", json={
            "message": "o que é essa tela?",
            "screen": {
                "route": "/obras/:id",
                "path": "/obras/123",
                "title": "Detalhe da obra",
                "module": "obras"
            }
        })
        assert resp.status_code == 200
        assert captured_inputs[0].screen_data is not None
        assert captured_inputs[0].screen_data["module"] == "obras"

    def test_copilot_disabled_returns_503(self):
        """When Arky is disabled, the endpoint should return 503."""
        user = _make_user()

        async def disabled_copilot():
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="Arky está desabilitado")

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_arky_copilot] = disabled_copilot

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/arky/chat", json={"message": "teste"})
        assert resp.status_code == 503


class TestChatStreamEndpoint:
    def test_stream_returns_sse_events_and_final_payload(self):
        user = _make_user()

        async def mock_chat_stream(inp):
            yield ArkyStreamEvent(type="status", status="recebendo_mensagem", label="Recebendo mensagem")
            yield ArkyStreamEvent(type="tool_start", status="chamando_tool", label="Consultando obras", tool_name="obras_list")
            yield ArkyStreamEvent(type="tool_end", status="tool_concluida", label="Consulta concluida", tool_name="obras_list", summary="2 obras encontradas")
            yield ArkyStreamEvent(type="final", status="finalizado", label="Finalizado", data=_make_chat_output())

        mock_copilot = MagicMock()
        mock_copilot.chat_stream = mock_chat_stream
        app = _build_app(user, copilot_mock=mock_copilot)
        client = TestClient(app)

        with client.stream("POST", "/arky/chat/stream", json={"message": "listar obras"}) as resp:
            body = "".join(resp.iter_text())

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "event: status" in body
        assert "recebendo_mensagem" in body
        assert "event: tool_start" in body
        assert "obras_list" in body
        assert "event: final" in body
        assert "Ol" in body

    def test_stream_uses_user_team_id_from_jwt(self):
        team_id = uuid4()
        user = _make_user(team_id=team_id)
        captured_inputs = []

        async def mock_chat_stream(inp):
            captured_inputs.append(inp)
            yield ArkyStreamEvent(type="final", status="finalizado", label="Finalizado", data=_make_chat_output())

        mock_copilot = MagicMock()
        mock_copilot.chat_stream = mock_chat_stream
        app = _build_app(user, copilot_mock=mock_copilot)
        client = TestClient(app)

        resp = client.post("/arky/chat/stream", json={"message": "teste"})

        assert resp.status_code == 200
        assert captured_inputs[0].team_id == team_id
        assert captured_inputs[0].user == user


class TestConfirmEndpoint:
    def _make_preview(self, team_id, user_id, status="pending"):
        from datetime import timedelta
        preview = object.__new__(ArkyActionPreview)
        preview.id = uuid4()
        preview.team_id = team_id
        preview.user_id = user_id
        preview.conversation_id = uuid4()
        preview.action_type = "prepare_create_obra"
        preview.payload = {"title": "Test"}
        preview.summary = "Criar obra"
        preview.risk_level = "preparacao"
        preview.status = status
        preview.expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        preview.confirmed_at = None
        preview.rejected_at = None
        preview.created_at = datetime.now(timezone.utc)
        return preview

    def _build_confirm_app(self, user, preview=None, not_found=False):
        app = FastAPI()
        app.include_router(router)

        mock_copilot = MagicMock()
        mock_copilot._uow = MagicMock()
        mock_copilot._uow.commit = AsyncMock()
        # Preview-only action types execute nothing on confirm.
        mock_copilot.execute_confirmed_action = AsyncMock(return_value=None)

        mock_preview_repo = MagicMock()
        if not_found or preview is None:
            mock_preview_repo.get_by_id = AsyncMock(return_value=None)
        else:
            mock_preview_repo.get_by_id = AsyncMock(return_value=preview)
            mock_preview_repo.update = AsyncMock(return_value=preview)

        mock_copilot._preview_repo = mock_preview_repo

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_arky_copilot] = lambda: mock_copilot

        return app

    def test_confirm_valid_preview(self):
        user = _make_user()
        preview = self._make_preview(user.team.id, user.id)

        app = self._build_confirm_app(user, preview)
        client = TestClient(app)

        resp = client.post(f"/arky/confirm/{preview.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"

    def test_confirm_nonexistent_preview_returns_404(self):
        user = _make_user()
        app = self._build_confirm_app(user, not_found=True)
        client = TestClient(app)

        resp = client.post(f"/arky/confirm/{uuid4()}")
        assert resp.status_code == 404

    def test_confirm_invalid_uuid_returns_400(self):
        user = _make_user()
        app = self._build_confirm_app(user, not_found=True)
        client = TestClient(app)

        resp = client.post("/arky/confirm/not-a-uuid")
        assert resp.status_code == 400

    def test_confirm_tenant_isolation(self):
        """Preview from another tenant must not be confirmable."""
        user = _make_user()
        # Preview with a different team_id than the user's
        other_team_id = uuid4()
        preview = self._make_preview(other_team_id, user.id)

        # Repository returns None because team_id doesn't match
        app = self._build_confirm_app(user, not_found=True)
        client = TestClient(app)

        resp = client.post(f"/arky/confirm/{preview.id}")
        assert resp.status_code == 404

    def test_confirm_already_confirmed_preview_returns_expired_or_message(self):
        user = _make_user()
        preview = self._make_preview(user.team.id, user.id, status="confirmed")

        app = self._build_confirm_app(user, preview)
        client = TestClient(app)

        resp = client.post(f"/arky/confirm/{preview.id}")
        assert resp.status_code == 200
        data = resp.json()
        # Returns without error but with a descriptive message
        assert "Ação expirou" in data["message"] or "já foi processada" in data["message"]


class TestRejectEndpoint:
    def _make_preview(self, team_id, user_id, status="pending"):
        from datetime import timedelta
        preview = object.__new__(ArkyActionPreview)
        preview.id = uuid4()
        preview.team_id = team_id
        preview.user_id = user_id
        preview.conversation_id = uuid4()
        preview.action_type = "prepare_create_obra"
        preview.payload = {"title": "Test"}
        preview.summary = "Criar obra"
        preview.risk_level = "preparacao"
        preview.status = status
        preview.expires_at = datetime.now(timezone.utc) + __import__("datetime").timedelta(minutes=15)
        preview.confirmed_at = None
        preview.rejected_at = None
        preview.created_at = datetime.now(timezone.utc)
        return preview

    def _build_reject_app(self, user, preview=None, not_found=False):
        app = FastAPI()
        app.include_router(router)

        mock_copilot = MagicMock()
        mock_copilot._uow = MagicMock()
        mock_copilot._uow.commit = AsyncMock()

        mock_preview_repo = MagicMock()
        if not_found or preview is None:
            mock_preview_repo.get_by_id = AsyncMock(return_value=None)
        else:
            mock_preview_repo.get_by_id = AsyncMock(return_value=preview)
            mock_preview_repo.update = AsyncMock(return_value=preview)

        mock_copilot._preview_repo = mock_preview_repo
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_arky_copilot] = lambda: mock_copilot

        return app

    def test_reject_valid_preview(self):
        user = _make_user()
        preview = self._make_preview(user.team.id, user.id)

        app = self._build_reject_app(user, preview)
        client = TestClient(app)

        resp = client.post(f"/arky/reject/{preview.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"

    def test_reject_nonexistent_preview_returns_404(self):
        user = _make_user()
        app = self._build_reject_app(user, not_found=True)
        client = TestClient(app)

        resp = client.post(f"/arky/reject/{uuid4()}")
        assert resp.status_code == 404

    def test_reject_already_rejected_returns_409(self):
        user = _make_user()
        preview = self._make_preview(user.team.id, user.id, status="rejected")

        app = self._build_reject_app(user, preview)
        client = TestClient(app)

        resp = client.post(f"/arky/reject/{preview.id}")
        assert resp.status_code == 409
