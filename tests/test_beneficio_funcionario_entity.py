from uuid import uuid4

from app.domain.entities.rh import BeneficioFuncionario, StatusBeneficio


def test_vinculo_nasce_ativo():
    v = BeneficioFuncionario(team_id=uuid4(), beneficio_id=uuid4(), funcionario_id=uuid4())
    assert v.status == StatusBeneficio.ATIVO
    assert v.is_deleted is False


def test_vinculo_inativar_e_reativar():
    v = BeneficioFuncionario(team_id=uuid4(), beneficio_id=uuid4(), funcionario_id=uuid4())
    v.inativar()
    assert v.status == StatusBeneficio.INATIVO
    v.ativar()
    assert v.status == StatusBeneficio.ATIVO


def test_vinculo_delete():
    v = BeneficioFuncionario(team_id=uuid4(), beneficio_id=uuid4(), funcionario_id=uuid4())
    v.delete()
    assert v.is_deleted is True
