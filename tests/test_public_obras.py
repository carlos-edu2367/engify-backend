from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.entities.financeiro import MovClass, MovimentacaoTypes, Natureza
from app.domain.entities.money import Money
from app.domain.entities.obra import Status
from app.http.routers import public_obras


class FakeRedis:
    def __init__(self):
        self.stored = {}

    async def get(self, key):
        return None

    async def set(self, key, value, ex=None):
        self.stored[key] = (value, ex)


class FakeStorage:
    async def get_signed_download_url(self, bucket, path, expires_in):
        return f"https://signed.example/{path}?ttl={expires_in}"


class FakeObraService:
    def __init__(self, obra):
        self.obra = obra

    async def get_obra(self, obra_id):
        return self.obra


class FakeItemService:
    async def list_items(self, obra_id):
        return []


class FakeImageService:
    async def list_by_obra(self, obra_id):
        return []


class FakeItemAttachmentService:
    async def list_by_item(self, item_id):
        return []


class FakeRecebimentoService:
    def __init__(self, entradas):
        self.entradas = entradas
        self.called_with = None

    async def list_entradas(self, obra_id, team_id, page, limit):
        self.called_with = (obra_id, team_id, page, limit)
        return self.entradas


class FakeFinanceiroService:
    def __init__(self, attachments_by_movimentacao):
        self.attachments_by_movimentacao = attachments_by_movimentacao

    async def get_attachments(self, movimentacao_id):
        return self.attachments_by_movimentacao.get(movimentacao_id, [])


@pytest.mark.asyncio
async def test_public_obra_includes_recebimentos_with_signed_attachments_without_values(monkeypatch):
    obra_id = uuid4()
    team_id = uuid4()
    recebimento_id = uuid4()
    attachment_id = uuid4()
    data_recebimento = datetime(2026, 6, 4, 12, 30, tzinfo=timezone.utc)

    fake_redis = FakeRedis()
    monkeypatch.setattr(public_obras, "get_redis", lambda: fake_redis)

    obra = SimpleNamespace(
        id=obra_id,
        team_id=team_id,
        title="Residencial Jardim",
        description="Acompanhamento publico",
        status=Status.EM_ANDAMENTO,
        data_entrega=None,
    )
    recebimento = SimpleNamespace(
        id=recebimento_id,
        team_id=team_id,
        obra_id=obra_id,
        title="Nota fiscal etapa 1",
        type=MovimentacaoTypes.ENTRADA,
        valor=Money(Decimal("2500.00")),
        classe=MovClass.CONTRATO,
        natureza=Natureza.MANUAL,
        data_movimentacao=data_recebimento,
        pagamento_id=None,
        lote_info=None,
        is_deleted=False,
    )
    attachment = SimpleNamespace(
        id=attachment_id,
        movimentacao_id=recebimento_id,
        team_id=team_id,
        file_path="financeiro/notas/nf-etapa-1.pdf",
        file_name="nf-etapa-1.pdf",
        content_type="application/pdf",
        created_at=data_recebimento,
    )
    rec_svc = FakeRecebimentoService([recebimento])

    response = await public_obras.get_obra_public(
        obra_id=obra_id,
        svc=FakeObraService(obra),
        item_svc=FakeItemService(),
        image_svc=FakeImageService(),
        att_svc=FakeItemAttachmentService(),
        rec_svc=rec_svc,
        financeiro_svc=FakeFinanceiroService({recebimento_id: [attachment]}),
        storage=FakeStorage(),
    )

    dumped = response.model_dump()
    assert rec_svc.called_with == (obra_id, team_id, 1, 1000)
    assert dumped["recebimentos"] == [
        {
            "id": recebimento_id,
            "title": "Nota fiscal etapa 1",
            "data_movimentacao": data_recebimento,
            "attachments": [
                {
                    "id": attachment_id,
                    "file_name": "nf-etapa-1.pdf",
                    "download_url": "https://signed.example/financeiro/notas/nf-etapa-1.pdf?ttl=3600",
                    "content_type": "application/pdf",
                }
            ],
        }
    ]
    public_payload = dumped["recebimentos"][0]
    assert "valor" not in public_payload
    assert "team_id" not in public_payload
    assert "file_path" not in public_payload["attachments"][0]
