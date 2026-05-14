from uuid import uuid4

import pytest

from app.application.dtos.obra import UpdateItem
from app.application.services.obra_service import ItemService
from app.domain.entities.obra import Item, Status
from app.domain.entities.user import Roles


class _FakeItemRepo:
    def __init__(self):
        self.saved = None

    async def save(self, item):
        self.saved = item
        return item


class _FakeUow:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_financeiro_can_finalize_item_from_financeiro_status():
    repo = _FakeItemRepo()
    uow = _FakeUow()
    service = ItemService(repo, uow)
    item = Item(
        title="Conferir pagamento",
        obra_id=uuid4(),
        team_id=uuid4(),
        status=Status.FINANCEIRO,
    )

    updated = await service.update_item(
        UpdateItem(status=Status.FINALIZADO),
        item,
        caller_role=Roles.FINANCEIRO.value,
    )

    assert updated.status == Status.FINALIZADO
    assert repo.saved is updated
    assert uow.committed is True
