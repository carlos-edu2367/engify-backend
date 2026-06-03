"""Unit tests for ArkyAuditService — sensitive data redaction."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.application.services.arky.audit_service import ArkyAuditService, _redact
from app.domain.entities.arky import ArkyAuditLog


class TestRedact:
    def test_redacts_cpf(self):
        data = {"cpf": "123.456.789-01", "other": "safe"}
        result = _redact(data)
        assert result["cpf"] == "***"
        assert result["other"] == "safe"

    def test_redacts_pix(self):
        data = {"pix": "chave_pix_value"}
        assert _redact(data)["pix"] == "***"

    def test_redacts_salario(self):
        data = {"salario": 5000}
        assert _redact(data)["salario"] == "***"

    def test_redacts_nested(self):
        data = {"user": {"cpf": "123", "nome": "John"}}
        result = _redact(data)
        assert result["user"]["cpf"] == "***"
        assert result["user"]["nome"] == "John"

    def test_redacts_list_items(self):
        data = [{"cpf": "123"}, {"nome": "safe"}]
        result = _redact(data)
        assert result[0]["cpf"] == "***"
        assert result[1]["nome"] == "safe"

    def test_leaves_safe_data_unchanged(self):
        data = {"title": "Test Obra", "status": "em_andamento", "id": "uuid123"}
        result = _redact(data)
        assert result == data

    def test_redacts_lat_lng(self):
        data = {"latitude": -23.5, "longitude": -46.6}
        result = _redact(data)
        assert result["latitude"] == "***"
        assert result["longitude"] == "***"


@pytest.mark.asyncio
class TestAuditService:
    async def test_record_saves_and_commits(self):
        audit_repo = MagicMock()
        audit_repo.save = AsyncMock(return_value=None)
        uow = MagicMock()
        uow.commit = AsyncMock()

        service = ArkyAuditService(audit_repo=audit_repo, uow=uow)

        log = ArkyAuditLog(
            team_id=uuid4(),
            user_id=uuid4(),
            user_role="admin",
            conversation_id=uuid4(),
            message_id=uuid4(),
            route="/obras",
            status="ok",
            tool_params_masked={"cpf": "123", "title": "Test"},
        )

        await service.record(log)

        audit_repo.save.assert_called_once()
        uow.commit.assert_called_once()
        # cpf must have been redacted before saving
        assert log.tool_params_masked["cpf"] == "***"
        assert log.tool_params_masked["title"] == "Test"

    async def test_record_never_raises_on_failure(self):
        """Audit failure must never break the user flow."""
        audit_repo = MagicMock()
        audit_repo.save = AsyncMock(side_effect=Exception("DB error"))
        uow = MagicMock()
        uow.commit = AsyncMock()

        service = ArkyAuditService(audit_repo=audit_repo, uow=uow)
        log = ArkyAuditLog(
            team_id=uuid4(),
            user_id=uuid4(),
            user_role="admin",
            conversation_id=uuid4(),
            message_id=uuid4(),
            route="/obras",
            status="ok",
        )

        # Must not raise
        await service.record(log)
