from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.services.rh_audit_service import RhAuditService
from app.domain.entities.rh import RhAuditLog


@pytest.mark.asyncio
async def test_rh_audit_service_masks_sensitive_fields_before_persisting():
    repo = AsyncMock()
    uow = AsyncMock()
    repo.save = AsyncMock(side_effect=lambda event: event)
    service = RhAuditService(audit_repo=repo, uow=uow)

    event = RhAuditLog(
        team_id=uuid4(),
        actor_user_id=uuid4(),
        actor_role="admin",
        entity_type="funcionario",
        entity_id=uuid4(),
        action="rh.funcionario.updated",
        before={"cpf": "52998224725", "salario_base": "5000.00", "file_path": "/tmp/a.pdf"},
        after={
            "cpf": "11144477735",
            "salary_snapshot": "5200.00",
            "latitude": -16.68,
            "nested": {"download_url": "https://signed", "longitude": -49.26},
        },
    )

    saved = await service.record(event)

    assert saved.before == {"cpf": "***4725", "salario_base": "***", "file_path": "***"}
    assert saved.after == {
        "cpf": "***7735",
        "salary_snapshot": "***",
        "latitude": "***",
        "nested": {"download_url": "***", "longitude": "***"},
    }
    uow.commit.assert_awaited_once()
