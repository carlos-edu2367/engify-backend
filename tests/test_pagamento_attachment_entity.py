from uuid import uuid4
from app.domain.entities.financeiro import PagamentoAttachment


def test_novo_anexo_comeca_nao_deletado():
    att = PagamentoAttachment(
        pagamento_id=uuid4(), team_id=uuid4(),
        file_path="pagamento/x/y.pdf", file_name="nota.pdf",
        content_type="application/pdf",
    )
    assert att.is_deleted is False
    assert att.id is None


def test_delete_marca_como_deletado():
    att = PagamentoAttachment(
        pagamento_id=uuid4(), team_id=uuid4(),
        file_path="pagamento/x/y.pdf", file_name="nota.pdf",
        content_type="application/pdf",
    )
    att.delete()
    assert att.is_deleted is True
