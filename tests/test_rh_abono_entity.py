from datetime import date
from uuid import uuid4

import pytest

from app.domain.entities.rh_abono import AbonoFalta
from app.domain.errors import DomainError


def test_abono_sem_motivo_levanta_erro():
    with pytest.raises(DomainError):
        AbonoFalta(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            data=date(2026, 3, 12),
            motivo="   ",
        )


def test_abono_guarda_motivo_sem_espacos_nas_pontas():
    abono = AbonoFalta(
        team_id=uuid4(),
        funcionario_id=uuid4(),
        data=date(2026, 3, 12),
        motivo="  Atestado entregue fora do prazo  ",
    )

    assert abono.motivo == "Atestado entregue fora do prazo"
    assert abono.is_deleted is False


def test_abono_recusa_motivo_maior_que_o_limite_da_coluna():
    with pytest.raises(DomainError):
        AbonoFalta(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            data=date(2026, 3, 12),
            motivo="x" * 256,
        )


def test_revogar_marca_como_deletado():
    abono = AbonoFalta(
        team_id=uuid4(),
        funcionario_id=uuid4(),
        data=date(2026, 3, 12),
        motivo="Falta justificada pelo gestor",
    )

    abono.revogar()

    assert abono.is_deleted is True
