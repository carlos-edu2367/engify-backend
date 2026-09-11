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


def test_abono_sem_minutos_abona_o_dia_inteiro():
    abono = AbonoFalta(team_id=uuid4(), funcionario_id=uuid4(), data=date(2026, 3, 12), motivo="Atestado")

    assert abono.minutos is None
    assert abono.dia_inteiro is True


def test_abono_de_horas_guarda_os_minutos_perdoados():
    abono = AbonoFalta(
        team_id=uuid4(), funcionario_id=uuid4(), data=date(2026, 3, 12), motivo="Consulta medica", minutos=90
    )

    assert abono.minutos == 90
    assert abono.dia_inteiro is False


@pytest.mark.parametrize("minutos", [0, -5, 24 * 60 + 1])
def test_abono_recusa_minutos_fora_de_um_dia(minutos):
    with pytest.raises(DomainError):
        AbonoFalta(team_id=uuid4(), funcionario_id=uuid4(), data=date(2026, 3, 12), motivo="Atestado", minutos=minutos)


def test_separar_abonos_soma_horas_do_mesmo_dia_e_isola_o_dia_inteiro():
    from decimal import Decimal

    from app.domain.entities.rh_abono import separar_abonos

    team_id, ana, bruno = uuid4(), uuid4(), uuid4()
    dia = date(2026, 3, 12)
    abonos = [
        AbonoFalta(team_id=team_id, funcionario_id=ana, data=dia, motivo="Consulta", minutos=60),
        AbonoFalta(team_id=team_id, funcionario_id=ana, data=dia, motivo="Transito", minutos=30),
        AbonoFalta(team_id=team_id, funcionario_id=bruno, data=dia, motivo="Atestado"),
    ]

    datas, minutos = separar_abonos(abonos)

    assert datas == {bruno: {dia}}
    assert minutos == {ana: {dia: Decimal("90")}}
