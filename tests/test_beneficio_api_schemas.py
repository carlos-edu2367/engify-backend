from decimal import Decimal
from uuid import uuid4

from app.http.schemas.rh import (
    RhBeneficioCreateRequest,
    RhBeneficioResponse,
    RhBeneficioFuncionarioAssignRequest,
    RhBeneficioFuncionarioResponse,
)
from app.domain.entities.rh import StatusBeneficio


def test_create_request_default_valor_dia():
    req = RhBeneficioCreateRequest(nome="VR")
    assert req.valor_dia == Decimal("0.00")


def test_create_request_accepts_valor_dia():
    req = RhBeneficioCreateRequest(nome="VR", valor_dia="25.50")
    assert req.valor_dia == Decimal("25.50")


def test_assign_request_parses_uuid():
    fid = uuid4()
    req = RhBeneficioFuncionarioAssignRequest(funcionario_id=str(fid))
    assert req.funcionario_id == fid


def test_funcionario_response_shape():
    resp = RhBeneficioFuncionarioResponse(id=uuid4(), beneficio_id=uuid4(), funcionario_id=uuid4(), status=StatusBeneficio.ATIVO)
    assert resp.status == StatusBeneficio.ATIVO
