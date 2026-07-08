from datetime import date, time
from uuid import uuid4

import pytest

from app.domain.entities.rh_calendario import EventoCalendarioRh, TipoEventoCalendario
from app.domain.errors import DomainError


def test_liberacao_antecipada_sem_hora_corte_levanta_erro():
    with pytest.raises(DomainError):
        EventoCalendarioRh(
            team_id=uuid4(),
            tipo=TipoEventoCalendario.LIBERACAO_ANTECIPADA,
            data=date(2026, 12, 24),
            descricao="Vespera de Natal",
        )


def test_feriado_nao_aceita_hora_corte():
    with pytest.raises(DomainError):
        EventoCalendarioRh(
            team_id=uuid4(),
            tipo=TipoEventoCalendario.FERIADO,
            data=date(2026, 12, 25),
            descricao="Natal",
            hora_corte=time(15, 0),
        )


def test_feriado_cria_ok_aplicando_a_todos():
    evento = EventoCalendarioRh(
        team_id=uuid4(),
        tipo=TipoEventoCalendario.FERIADO,
        data=date(2026, 12, 25),
        descricao="Natal",
    )
    assert evento.aplica_todos is True
    assert evento.aplica_a(uuid4()) is True


def test_abono_por_funcionario_especifico():
    funcionario_id = uuid4()
    evento = EventoCalendarioRh(
        team_id=uuid4(),
        tipo=TipoEventoCalendario.ABONO,
        data=date(2026, 6, 10),
        descricao="Atestado externo aceito manualmente",
        aplica_todos=False,
        funcionario_ids=[funcionario_id],
    )
    assert evento.aplica_a(funcionario_id) is True
    assert evento.aplica_a(uuid4()) is False


def test_evento_sem_escopo_e_sem_funcionarios_levanta_erro():
    with pytest.raises(DomainError):
        EventoCalendarioRh(
            team_id=uuid4(),
            tipo=TipoEventoCalendario.ABONO,
            data=date(2026, 6, 10),
            descricao="Abono sem destinatario",
            aplica_todos=False,
            funcionario_ids=[],
        )


def test_liberacao_antecipada_com_hora_corte_cria_ok():
    evento = EventoCalendarioRh(
        team_id=uuid4(),
        tipo=TipoEventoCalendario.LIBERACAO_ANTECIPADA,
        data=date(2026, 12, 24),
        descricao="Vespera de Natal - liberacao as 15h",
        hora_corte=time(15, 0),
    )
    assert evento.hora_corte == time(15, 0)
