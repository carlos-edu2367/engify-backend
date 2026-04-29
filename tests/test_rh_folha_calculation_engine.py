from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.money import Money
from app.domain.entities.rh import (
    BaseCalculoEncargo,
    EscopoAplicabilidade,
    FaixaEncargo,
    FolhaCalculationContext,
    HoleriteItem,
    HoleriteItemNatureza,
    HoleriteItemTipo,
    NaturezaEncargo,
    RegraEncargo,
    RegraEncargoAplicabilidade,
    StatusRegraEncargo,
    TabelaProgressiva,
    TipoRegraEncargo,
)


def _build_context():
    team_id = uuid4()
    funcionario_id = uuid4()
    itens = [
        HoleriteItem(
            team_id=team_id,
            holerite_id=uuid4(),
            funcionario_id=funcionario_id,
            tipo=HoleriteItemTipo.SALARIO_BASE,
            origem="sistema",
            codigo="SALARIO_BASE",
            descricao="Salario Base",
            natureza=HoleriteItemNatureza.PROVENTO,
            ordem=100,
            base=Money(Decimal("2000.00")),
            valor=Money(Decimal("2000.00")),
        )
    ]
    return FolhaCalculationContext(
        team_id=team_id,
        holerite_id=itens[0].holerite_id,
        funcionario_id=funcionario_id,
        competencia_mes=4,
        competencia_ano=2026,
        salario_base=Money(Decimal("2000.00")),
        horas_extras=Money(Decimal("0.00")),
        descontos_falta=Money(Decimal("0.00")),
        acrescimos_manuais=Money(Decimal("0.00")),
        descontos_manuais=Money(Decimal("0.00")),
        bruto_antes_encargos=Money(Decimal("2000.00")),
        bruto_antes_irrf=Money(Decimal("2000.00")),
        liquido_parcial=Money(Decimal("2000.00")),
        itens=itens,
    )


def test_engine_without_rules_returns_same_totals():
    from app.domain.services.rh_folha_calculation_engine import FolhaCalculationEngine

    context = _build_context()

    result = FolhaCalculationEngine().apply(context, [])

    assert len(result.itens) == 1
    assert result.total_proventos.amount == Decimal("2000.00")
    assert result.total_descontos.amount == Decimal("0.00")
    assert result.total_informativos.amount == Decimal("0.00")
    assert result.valor_bruto.amount == Decimal("2000.00")
    assert result.valor_liquido.amount == Decimal("2000.00")


def test_engine_applies_fixed_provento_rule_without_touching_existing_base_math():
    from app.domain.services.rh_folha_calculation_engine import FolhaCalculationEngine

    context = _build_context()
    regra = RegraEncargo(
        team_id=context.team_id,
        codigo="VA",
        nome="Vale Alimentacao",
        tipo_calculo=TipoRegraEncargo.VALOR_FIXO,
        natureza=NaturezaEncargo.PROVENTO,
        base_calculo=BaseCalculoEncargo.VALOR_REFERENCIA_MANUAL,
        prioridade=500,
        valor_fixo=Money(Decimal("500.00")),
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    result = FolhaCalculationEngine().apply(context, [regra])

    assert [item.codigo for item in result.itens] == ["SALARIO_BASE", "VA"]
    assert result.total_proventos.amount == Decimal("2500.00")
    assert result.total_descontos.amount == Decimal("0.00")
    assert result.valor_liquido.amount == Decimal("2500.00")


def test_engine_applies_fixed_discount_rule():
    from app.domain.services.rh_folha_calculation_engine import FolhaCalculationEngine

    context = _build_context()
    regra = RegraEncargo(
        team_id=context.team_id,
        codigo="VR",
        nome="Vale Refeicao",
        tipo_calculo=TipoRegraEncargo.VALOR_FIXO,
        natureza=NaturezaEncargo.DESCONTO,
        base_calculo=BaseCalculoEncargo.VALOR_REFERENCIA_MANUAL,
        prioridade=500,
        valor_fixo=Money(Decimal("120.00")),
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    result = FolhaCalculationEngine().apply(context, [regra])

    assert result.total_descontos.amount == Decimal("120.00")
    assert result.valor_liquido.amount == Decimal("1880.00")
    assert result.itens[-1].snapshot_calculo["valor"] == "120.00"


def test_engine_applies_percentual_simples_with_informativo_nature():
    from app.domain.services.rh_folha_calculation_engine import FolhaCalculationEngine

    context = _build_context()
    regra = RegraEncargo(
        team_id=context.team_id,
        codigo="FGTS",
        nome="FGTS",
        tipo_calculo=TipoRegraEncargo.PERCENTUAL_SIMPLES,
        natureza=NaturezaEncargo.INFORMATIVO,
        base_calculo=BaseCalculoEncargo.BRUTO_ANTES_ENCARGOS,
        prioridade=1000,
        percentual=Decimal("8.00"),
        incide_no_liquido=False,
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    result = FolhaCalculationEngine().apply(context, [regra])

    assert result.total_informativos.amount == Decimal("160.00")
    assert result.valor_liquido.amount == Decimal("2000.00")
    assert result.itens[-1].natureza == HoleriteItemNatureza.INFORMATIVO


def test_engine_applies_progressive_inss_with_marginal_brackets():
    from app.domain.services.rh_folha_calculation_engine import FolhaCalculationEngine

    context = _build_context()
    context.salario_base = Money(Decimal("5000.00"))
    context.itens[0].base = Money(Decimal("5000.00"))
    context.itens[0].valor = Money(Decimal("5000.00"))
    context.bruto_antes_encargos = Money(Decimal("5000.00"))
    context.bruto_antes_irrf = Money(Decimal("5000.00"))
    context.liquido_parcial = Money(Decimal("5000.00"))
    tabela = TabelaProgressiva(
        team_id=context.team_id,
        codigo="INSS_2026",
        nome="INSS 2026",
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
        faixas=[
            FaixaEncargo(
                team_id=context.team_id,
                ordem=1,
                valor_inicial=Money(Decimal("0.00")),
                valor_final=Money(Decimal("2000.00")),
                aliquota=Decimal("10.00"),
                calculo_marginal=True,
            ),
            FaixaEncargo(
                team_id=context.team_id,
                ordem=2,
                valor_inicial=Money(Decimal("2000.00")),
                valor_final=Money(Decimal("5000.00")),
                aliquota=Decimal("15.00"),
                calculo_marginal=True,
            ),
        ],
    )
    regra = RegraEncargo(
        team_id=context.team_id,
        codigo="INSS",
        nome="INSS",
        tipo_calculo=TipoRegraEncargo.TABELA_PROGRESSIVA,
        natureza=NaturezaEncargo.DESCONTO,
        base_calculo=BaseCalculoEncargo.BRUTO_ANTES_ENCARGOS,
        prioridade=600,
        tabela_progressiva_id=tabela.id,
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    regra.tabela_progressiva = tabela

    result = FolhaCalculationEngine().apply(context, [regra])

    assert result.total_descontos.amount == Decimal("650.00")
    assert result.valor_liquido.amount == Decimal("4350.00")
    assert result.itens[-1].snapshot_calculo["faixa_aplicada"]["ordem"] == 2
    assert result.itens[-1].snapshot_calculo["tabela"]["codigo"] == "INSS_2026"


def test_engine_applies_irrf_using_base_reduced_by_previous_inss():
    from app.domain.services.rh_folha_calculation_engine import FolhaCalculationEngine

    context = _build_context()
    context.salario_base = Money(Decimal("5000.00"))
    context.bruto_antes_encargos = Money(Decimal("5000.00"))
    context.bruto_antes_irrf = Money(Decimal("5000.00"))
    context.liquido_parcial = Money(Decimal("5000.00"))
    inss_tabela = TabelaProgressiva(
        team_id=context.team_id,
        codigo="INSS_2026",
        nome="INSS 2026",
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
        faixas=[
            FaixaEncargo(
                team_id=context.team_id,
                ordem=1,
                valor_inicial=Money(Decimal("0.00")),
                valor_final=Money(Decimal("5000.00")),
                aliquota=Decimal("11.00"),
                calculo_marginal=False,
            ),
        ],
    )
    irrf_tabela = TabelaProgressiva(
        team_id=context.team_id,
        codigo="IRRF_2026",
        nome="IRRF 2026",
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
        faixas=[
            FaixaEncargo(
                team_id=context.team_id,
                ordem=1,
                valor_inicial=Money(Decimal("0.00")),
                valor_final=Money(Decimal("10000.00")),
                aliquota=Decimal("15.00"),
                deducao=Money(Decimal("100.00")),
                calculo_marginal=False,
            ),
        ],
    )
    inss = RegraEncargo(
        team_id=context.team_id,
        codigo="INSS",
        nome="INSS",
        tipo_calculo=TipoRegraEncargo.TABELA_PROGRESSIVA,
        natureza=NaturezaEncargo.DESCONTO,
        base_calculo=BaseCalculoEncargo.BRUTO_ANTES_ENCARGOS,
        prioridade=600,
        tabela_progressiva_id=inss_tabela.id,
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    inss.tabela_progressiva = inss_tabela
    irrf = RegraEncargo(
        team_id=context.team_id,
        codigo="IRRF",
        nome="IRRF",
        tipo_calculo=TipoRegraEncargo.TABELA_PROGRESSIVA,
        natureza=NaturezaEncargo.DESCONTO,
        base_calculo=BaseCalculoEncargo.BRUTO_ANTES_IRRF,
        prioridade=700,
        tabela_progressiva_id=irrf_tabela.id,
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    irrf.tabela_progressiva = irrf_tabela

    result = FolhaCalculationEngine().apply(context, [inss, irrf])

    assert [item.codigo for item in result.itens[-2:]] == ["INSS", "IRRF"]
    assert result.itens[-2].valor.amount == Decimal("550.00")
    assert result.itens[-1].base.amount == Decimal("4450.00")
    assert result.itens[-1].valor.amount == Decimal("567.50")


def test_engine_prefers_specific_rule_over_general_rule_for_same_code():
    from app.domain.services.rh_folha_calculation_engine import FolhaCalculationEngine

    context = _build_context()
    geral = RegraEncargo(
        team_id=context.team_id,
        codigo="VT",
        nome="Vale Transporte Geral",
        tipo_calculo=TipoRegraEncargo.PERCENTUAL_SIMPLES,
        natureza=NaturezaEncargo.DESCONTO,
        base_calculo=BaseCalculoEncargo.SALARIO_BASE,
        prioridade=800,
        percentual=Decimal("6.00"),
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
        aplicabilidades=[
            RegraEncargoAplicabilidade(
                team_id=context.team_id,
                escopo=EscopoAplicabilidade.TODOS_FUNCIONARIOS,
            )
        ],
    )
    especifica = RegraEncargo(
        team_id=context.team_id,
        codigo="VT",
        nome="Vale Transporte Ana",
        tipo_calculo=TipoRegraEncargo.PERCENTUAL_SIMPLES,
        natureza=NaturezaEncargo.DESCONTO,
        base_calculo=BaseCalculoEncargo.SALARIO_BASE,
        prioridade=800,
        percentual=Decimal("4.00"),
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
        aplicabilidades=[
            RegraEncargoAplicabilidade(
                team_id=context.team_id,
                escopo=EscopoAplicabilidade.POR_FUNCIONARIO,
                valor=str(context.funcionario_id),
            )
        ],
    )

    result = FolhaCalculationEngine().apply(context, [geral, especifica])

    assert [item.codigo for item in result.itens] == ["SALARIO_BASE", "VT"]
    assert result.itens[-1].descricao == "Vale Transporte Ana"
    assert result.itens[-1].valor.amount == Decimal("80.00")
