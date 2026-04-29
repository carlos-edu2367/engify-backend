from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.user import Roles


def test_roles_has_funcionario():
    assert Roles.FUNCIONARIO.value == "funcionario"


def test_turno_horario_rejects_invalid_week_day():
    from app.domain.entities.rh import TurnoHorario

    with pytest.raises(Exception):
        TurnoHorario(dia_semana=7, hora_entrada=time(8, 0), hora_saida=time(17, 0))


def test_turno_horario_rejects_invalid_time_range():
    from app.domain.entities.rh import TurnoHorario

    with pytest.raises(Exception):
        TurnoHorario(dia_semana=0, hora_entrada=time(17, 0), hora_saida=time(8, 0))


def test_turno_horario_without_interval_keeps_expected_hours():
    from app.domain.entities.rh import TurnoHorario

    turno = TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))

    assert turno.horas_esperadas == 9


def test_turno_horario_with_interval_discounts_expected_hours():
    from app.domain.entities.rh import IntervaloHorario, TurnoHorario

    turno = TurnoHorario(
        dia_semana=0,
        hora_entrada=time(8, 0),
        hora_saida=time(17, 0),
        intervalos=[IntervaloHorario(hora_inicio=time(12, 0), hora_fim=time(13, 0))],
    )

    assert turno.horas_esperadas == 8


def test_turno_horario_rejects_interval_outside_shift():
    from app.domain.entities.rh import IntervaloHorario, TurnoHorario

    with pytest.raises(Exception):
        TurnoHorario(
            dia_semana=0,
            hora_entrada=time(8, 0),
            hora_saida=time(17, 0),
            intervalos=[IntervaloHorario(hora_inicio=time(7, 30), hora_fim=time(8, 30))],
        )


def test_turno_horario_rejects_overlapping_intervals():
    from app.domain.entities.rh import IntervaloHorario, TurnoHorario

    with pytest.raises(Exception):
        TurnoHorario(
            dia_semana=0,
            hora_entrada=time(8, 0),
            hora_saida=time(17, 0),
            intervalos=[
                IntervaloHorario(hora_inicio=time(12, 0), hora_fim=time(13, 0)),
                IntervaloHorario(hora_inicio=time(12, 30), hora_fim=time(13, 30)),
            ],
        )


def test_horario_trabalho_requires_turnos():
    from app.domain.entities.rh import HorarioTrabalho

    with pytest.raises(Exception):
        HorarioTrabalho(team_id=uuid4(), funcionario_id=uuid4(), turnos=[])


def test_horario_trabalho_rejects_duplicate_week_day():
    from app.domain.entities.rh import HorarioTrabalho, TurnoHorario

    with pytest.raises(Exception):
        HorarioTrabalho(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            turnos=[
                TurnoHorario(0, time(8, 0), time(12, 0)),
                TurnoHorario(0, time(13, 0), time(17, 0)),
            ],
        )


def test_funcionario_rejects_empty_nome():
    from app.domain.entities.rh import Funcionario

    with pytest.raises(Exception):
        Funcionario(
            team_id=uuid4(),
            nome="",
            cpf=CPF("52998224725"),
            cargo="Engenheiro",
            salario_base=Money(Decimal("1000.00")),
            data_admissao=datetime.now(timezone.utc),
        )


def test_funcionario_rejects_negative_salary():
    from app.domain.entities.rh import Funcionario

    with pytest.raises(Exception):
        Funcionario(
            team_id=uuid4(),
            nome="Carlos",
            cpf=CPF("52998224725"),
            cargo="Engenheiro",
            salario_base=Money(Decimal("-1.00")),
            data_admissao=datetime.now(timezone.utc),
        )


def test_ferias_rejects_invalid_period():
    from app.domain.entities.rh import Ferias

    now = datetime.now(timezone.utc)
    with pytest.raises(Exception):
        Ferias(team_id=uuid4(), funcionario_id=uuid4(), data_inicio=now, data_fim=now)


def test_local_ponto_rejects_invalid_coordinates_and_radius():
    from app.domain.entities.rh import LocalPonto

    with pytest.raises(Exception):
        LocalPonto(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            nome="Obra 1",
            latitude=-91,
            longitude=10,
            raio_metros=100,
        )

    with pytest.raises(Exception):
        LocalPonto(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            nome="Obra 1",
            latitude=-10,
            longitude=181,
            raio_metros=100,
        )

    with pytest.raises(Exception):
        LocalPonto(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            nome="Obra 1",
            latitude=-10,
            longitude=10,
            raio_metros=0,
        )


def test_atestado_rejects_invalid_period():
    from app.domain.entities.rh import Atestado

    start = datetime(2026, 1, 2, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(Exception):
        Atestado(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            tipo_atestado_id=uuid4(),
            data_inicio=start,
            data_fim=end,
        )


def test_ajuste_ponto_requires_justificativa_and_requested_time():
    from app.domain.entities.rh import AjustePonto

    with pytest.raises(Exception):
        AjustePonto(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            data_referencia=datetime(2026, 4, 28, tzinfo=timezone.utc),
            justificativa="",
            hora_entrada_solicitada=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
        )

    with pytest.raises(Exception):
        AjustePonto(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            data_referencia=datetime(2026, 4, 28, tzinfo=timezone.utc),
            justificativa="Esqueci de bater ponto",
        )


def test_rejecting_requests_requires_reason():
    from app.domain.entities.rh import AjustePonto, Atestado, Ferias

    ferias = Ferias(
        team_id=uuid4(),
        funcionario_id=uuid4(),
        data_inicio=datetime(2026, 5, 1, tzinfo=timezone.utc),
        data_fim=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )
    ajuste = AjustePonto(
        team_id=uuid4(),
        funcionario_id=uuid4(),
        data_referencia=datetime(2026, 4, 28, tzinfo=timezone.utc),
        justificativa="Esqueci de bater ponto",
        hora_entrada_solicitada=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
    )
    atestado = Atestado(
        team_id=uuid4(),
        funcionario_id=uuid4(),
        tipo_atestado_id=uuid4(),
        data_inicio=datetime(2026, 4, 28, tzinfo=timezone.utc),
        data_fim=datetime(2026, 4, 28, tzinfo=timezone.utc),
    )

    with pytest.raises(Exception):
        ferias.rejeitar("")
    with pytest.raises(Exception):
        ajuste.rejeitar("")
    with pytest.raises(Exception):
        atestado.rejeitar("")


def test_tipo_atestado_rejects_invalid_name_and_deadline():
    from app.domain.entities.rh import TipoAtestado

    with pytest.raises(Exception):
        TipoAtestado(team_id=uuid4(), nome="", prazo_entrega_dias=2)

    with pytest.raises(Exception):
        TipoAtestado(team_id=uuid4(), nome="Medico", prazo_entrega_dias=-1)


def test_holerite_fechar_sets_status_and_pagamento():
    from app.domain.entities.rh import Holerite, StatusHolerite

    holerite = Holerite(
        team_id=uuid4(),
        funcionario_id=uuid4(),
        mes_referencia=4,
        ano_referencia=2026,
        salario_base=Money(Decimal("1000.00")),
        horas_extras=Money(Decimal("100.00")),
        descontos_falta=Money(Decimal("50.00")),
        acrescimos_manuais=Money(Decimal("0.00")),
        descontos_manuais=Money(Decimal("0.00")),
        valor_liquido=Money(Decimal("1050.00")),
    )
    pagamento_id = uuid4()

    holerite.fechar(pagamento_id)

    assert holerite.status == StatusHolerite.FECHADO
    assert holerite.pagamento_agendado_id == pagamento_id


def test_holerite_rejects_invalid_competencia():
    from app.domain.entities.rh import Holerite

    with pytest.raises(Exception):
        Holerite(
            team_id=uuid4(),
            funcionario_id=uuid4(),
            mes_referencia=13,
            ano_referencia=2026,
            salario_base=Money(Decimal("1000.00")),
            horas_extras=Money(Decimal("0.00")),
            descontos_falta=Money(Decimal("0.00")),
            acrescimos_manuais=Money(Decimal("0.00")),
            descontos_manuais=Money(Decimal("0.00")),
            valor_liquido=Money(Decimal("1000.00")),
        )


def test_holerite_recalcula_liquido_ao_atualizar_ajustes_manuais():
    from app.domain.entities.rh import Holerite

    holerite = Holerite(
        team_id=uuid4(),
        funcionario_id=uuid4(),
        mes_referencia=4,
        ano_referencia=2026,
        salario_base=Money(Decimal("1000.00")),
        horas_extras=Money(Decimal("100.00")),
        descontos_falta=Money(Decimal("50.00")),
        acrescimos_manuais=Money(Decimal("0.00")),
        descontos_manuais=Money(Decimal("0.00")),
        valor_liquido=Money(Decimal("1050.00")),
    )

    holerite.atualizar_ajustes_manuais(
        Money(Decimal("25.00")),
        Money(Decimal("10.00")),
    )

    assert holerite.acrescimos_manuais.amount == Decimal("25.00")
    assert holerite.descontos_manuais.amount == Decimal("10.00")
    assert holerite.valor_liquido.amount == Decimal("1065.00")


def test_delete_marks_entities_as_deleted():
    from app.domain.entities.rh import Funcionario, HorarioTrabalho, TurnoHorario

    funcionario = Funcionario(
        team_id=uuid4(),
        nome="Carlos",
        cpf=CPF("52998224725"),
        cargo="Engenheiro",
        salario_base=Money(Decimal("1000.00")),
        data_admissao=datetime.now(timezone.utc),
    )
    horario = HorarioTrabalho(
        team_id=uuid4(),
        funcionario_id=uuid4(),
        turnos=[TurnoHorario(0, time(8, 0), time(17, 0))],
    )

    funcionario.delete()
    horario.delete()

    assert funcionario.is_deleted is True
    assert horario.is_deleted is True
