"""Testes da flag 'necessita de comprovante' e da marcacao de receipt_attached."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.financeiro import (
    MovClass, MovimentacaoAttachment, PagamentoAgendado,
)
from app.domain.entities.money import Money


def test_pagamento_tem_flags_de_comprovante_desligadas_por_padrao(team_id):
    p = PagamentoAgendado(
        team_id=team_id, title="X", details="", valor=Money(Decimal("10.00")),
        data_agendada=datetime.now(timezone.utc), classe=MovClass.SERVICO,
    )
    assert p.requires_receipt is False
    assert p.receipt_attached is False


def test_pagamento_aceita_requires_receipt(team_id):
    p = PagamentoAgendado(
        team_id=team_id, title="X", details="", valor=Money(Decimal("10.00")),
        data_agendada=datetime.now(timezone.utc), classe=MovClass.SERVICO,
        requires_receipt=True,
    )
    assert p.requires_receipt is True


def test_anexo_de_movimentacao_nasce_como_documento(team_id):
    a = MovimentacaoAttachment(
        movimentacao_id=uuid4(), team_id=team_id, file_path="p",
        file_name="n.pdf", content_type="application/pdf",
    )
    assert a.kind == "documento"
    assert a.origem_pagamento_id is None


def test_anexo_de_movimentacao_aceita_comprovante_e_origem(team_id):
    origem = uuid4()
    a = MovimentacaoAttachment(
        movimentacao_id=uuid4(), team_id=team_id, file_path="p",
        file_name="n.pdf", content_type="application/pdf",
        kind="comprovante", origem_pagamento_id=origem,
    )
    assert a.kind == "comprovante"
    assert a.origem_pagamento_id == origem
