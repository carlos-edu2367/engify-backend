from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.domain.entities.money import Money
from app.domain.entities.rh import (
    BaseCalculoEncargo,
    EscopoAplicabilidade,
    FaixaEncargo,
    FolhaCalculationContext,
    FolhaCalculationResult,
    HoleriteItem,
    HoleriteItemNatureza,
    HoleriteItemTipo,
    NaturezaEncargo,
    RegraEncargo,
    TabelaProgressiva,
    TipoRegraEncargo,
)
from app.domain.errors import DomainError


class FolhaCalculationEngine:
    def apply(
        self,
        context: FolhaCalculationContext,
        regras: list[RegraEncargo],
    ) -> FolhaCalculationResult:
        itens = list(context.itens)
        liquido_parcial = context.liquido_parcial
        bruto_antes_irrf = context.bruto_antes_irrf
        regras_aplicaveis = self._resolver_regras_aplicaveis(context, regras)

        for regra in sorted(regras_aplicaveis, key=lambda item: (item.prioridade, item.codigo)):
            base = self._resolver_base(context, liquido_parcial, bruto_antes_irrf, regra.base_calculo)
            valor, snapshot_calculo = self._calcular_valor_regra(regra, base)
            item = self._criar_item(context, regra, base, valor, snapshot_calculo)
            itens.append(item)
            if item.natureza == HoleriteItemNatureza.PROVENTO:
                liquido_parcial = liquido_parcial + item.valor
            elif item.natureza == HoleriteItemNatureza.DESCONTO:
                liquido_parcial = liquido_parcial - item.valor
                bruto_antes_irrf = bruto_antes_irrf - item.valor

        return self._consolidar(itens)

    def _resolver_regras_aplicaveis(
        self,
        context: FolhaCalculationContext,
        regras: list[RegraEncargo],
    ) -> list[RegraEncargo]:
        candidatas = [regra for regra in regras if self._regra_aplica_para_contexto(context, regra)]
        if not candidatas:
            return []

        por_codigo: dict[str, list[RegraEncargo]] = defaultdict(list)
        for regra in candidatas:
            por_codigo[regra.codigo].append(regra)

        selecionadas: list[RegraEncargo] = []
        for codigo in sorted(por_codigo):
            grupo = por_codigo[codigo]
            grupo.sort(
                key=lambda regra: (
                    self._specificity_rank(regra),
                    -regra.prioridade,
                    regra.vigencia_inicio or 0,
                ),
                reverse=True,
            )
            selecionadas.append(grupo[0])
        return selecionadas

    def _regra_aplica_para_contexto(self, context: FolhaCalculationContext, regra: RegraEncargo) -> bool:
        if not regra.aplicabilidades:
            return True
        for aplicabilidade in regra.aplicabilidades:
            if aplicabilidade.escopo == EscopoAplicabilidade.TODOS_FUNCIONARIOS:
                return True
            if (
                aplicabilidade.escopo == EscopoAplicabilidade.POR_FUNCIONARIO
                and aplicabilidade.valor == str(context.funcionario_id)
            ):
                return True
        return False

    def _specificity_rank(self, regra: RegraEncargo) -> int:
        if not regra.aplicabilidades:
            return 0
        ranks = {
            EscopoAplicabilidade.TODOS_FUNCIONARIOS: 1,
            EscopoAplicabilidade.POR_CARGO: 2,
            EscopoAplicabilidade.POR_TIPO_CONTRATO: 2,
            EscopoAplicabilidade.POR_EMPRESA: 2,
            EscopoAplicabilidade.POR_TAG: 2,
            EscopoAplicabilidade.POR_FUNCIONARIO: 3,
        }
        return max(ranks.get(aplicabilidade.escopo, 0) for aplicabilidade in regra.aplicabilidades)

    def _resolver_base(
        self,
        context: FolhaCalculationContext,
        liquido_parcial: Money,
        bruto_antes_irrf: Money,
        base_calculo: BaseCalculoEncargo,
    ) -> Money:
        if base_calculo == BaseCalculoEncargo.SALARIO_BASE:
            return context.salario_base
        if base_calculo == BaseCalculoEncargo.SALARIO_BASE_MAIS_EXTRAS:
            return context.salario_base + context.horas_extras
        if base_calculo == BaseCalculoEncargo.BRUTO_ANTES_ENCARGOS:
            return context.bruto_antes_encargos
        if base_calculo == BaseCalculoEncargo.BRUTO_ANTES_IRRF:
            return bruto_antes_irrf
        if base_calculo == BaseCalculoEncargo.LIQUIDO_PARCIAL:
            return liquido_parcial
        if base_calculo == BaseCalculoEncargo.VALOR_REFERENCIA_MANUAL:
            return Money(Decimal("0.00"))
        raise DomainError("Base de calculo nao suportada")

    def _calcular_valor_regra(self, regra: RegraEncargo, base: Money) -> tuple[Money, dict]:
        if regra.tipo_calculo == TipoRegraEncargo.VALOR_FIXO:
            if regra.valor_fixo is None:
                raise DomainError("Regra fixa sem valor configurado")
            valor = self._aplicar_limites(regra, regra.valor_fixo)
            return valor, {
                "formula": "valor_fixo",
                "base": str(base.amount),
                "valor": str(valor.amount),
            }
        if regra.tipo_calculo == TipoRegraEncargo.PERCENTUAL_SIMPLES:
            if regra.percentual is None:
                raise DomainError("Regra percentual sem percentual configurado")
            valor = self._aplicar_limites(regra, base * (regra.percentual / Decimal("100")))
            return valor, {
                "formula": "percentual_simples",
                "base": str(base.amount),
                "aliquota": str(regra.percentual),
                "valor": str(valor.amount),
            }
        if regra.tipo_calculo == TipoRegraEncargo.TABELA_PROGRESSIVA:
            tabela = self._obter_tabela_progressiva(regra)
            return self._calcular_progressivo(regra, tabela, base)
        raise DomainError("Tipo de calculo de regra nao suportado")

    def _obter_tabela_progressiva(self, regra: RegraEncargo) -> TabelaProgressiva:
        tabela = getattr(regra, "tabela_progressiva", None)
        if tabela is None:
            raise DomainError("Regra progressiva sem tabela carregada")
        if not tabela.faixas:
            raise DomainError("Tabela progressiva sem faixas")
        return tabela

    def _calcular_progressivo(
        self,
        regra: RegraEncargo,
        tabela: TabelaProgressiva,
        base: Money,
    ) -> tuple[Money, dict]:
        faixas = sorted(tabela.faixas, key=lambda item: item.ordem)
        faixa_aplicada = self._resolver_faixa_aplicada(faixas, base)
        if faixa_aplicada is None:
            return Money(Decimal("0.00"), base.currency), {
                "tabela": {"codigo": tabela.codigo, "nome": tabela.nome},
                "base": str(base.amount),
                "valor": "0.00",
            }

        if any(faixa.calculo_marginal for faixa in faixas):
            valor_bruto = self._calcular_marginal(base, faixas)
            aliquota = faixa_aplicada.aliquota
            deducao = Money(Decimal("0.00"), base.currency)
        else:
            aliquota = faixa_aplicada.aliquota
            deducao = faixa_aplicada.deducao
            valor_bruto = (base * (aliquota / Decimal("100"))) - deducao

        valor = self._aplicar_limites(regra, valor_bruto if valor_bruto.amount > 0 else Money(Decimal("0.00"), base.currency))
        return valor, {
            "formula": "tabela_progressiva",
            "tabela": {
                "id": str(tabela.id),
                "codigo": tabela.codigo,
                "nome": tabela.nome,
            },
            "faixa_aplicada": {
                "ordem": faixa_aplicada.ordem,
                "valor_inicial": str(faixa_aplicada.valor_inicial.amount),
                "valor_final": str(faixa_aplicada.valor_final.amount) if faixa_aplicada.valor_final else None,
            },
            "base": str(base.amount),
            "aliquota": str(aliquota),
            "deducao": str(deducao.amount),
            "valor": str(valor.amount),
            "modo": "marginal" if any(faixa.calculo_marginal for faixa in faixas) else "aliquota_efetiva_deducao",
        }

    def _resolver_faixa_aplicada(self, faixas: list[FaixaEncargo], base: Money) -> FaixaEncargo | None:
        for faixa in faixas:
            final = faixa.valor_final.amount if faixa.valor_final is not None else None
            if base.amount >= faixa.valor_inicial.amount and (final is None or base.amount <= final):
                return faixa
        return None

    def _calcular_marginal(self, base: Money, faixas: list[FaixaEncargo]) -> Money:
        total = Money(Decimal("0.00"), base.currency)
        for faixa in faixas:
            if base.amount <= faixa.valor_inicial.amount:
                continue
            limite_superior = faixa.valor_final.amount if faixa.valor_final is not None else base.amount
            parcela = min(base.amount, limite_superior) - faixa.valor_inicial.amount
            if parcela <= 0:
                continue
            total = total + Money(parcela, base.currency) * (faixa.aliquota / Decimal("100"))
            if faixa.valor_final is None or base.amount <= limite_superior:
                break
        return total

    def _aplicar_limites(self, regra: RegraEncargo, valor: Money) -> Money:
        ajustado = valor
        if regra.piso is not None and ajustado < regra.piso:
            ajustado = regra.piso
        if regra.teto is not None and ajustado > regra.teto:
            ajustado = regra.teto
        return ajustado

    def _criar_item(
        self,
        context: FolhaCalculationContext,
        regra: RegraEncargo,
        base: Money,
        valor: Money,
        snapshot_calculo: dict,
    ) -> HoleriteItem:
        natureza = {
            NaturezaEncargo.PROVENTO: HoleriteItemNatureza.PROVENTO,
            NaturezaEncargo.DESCONTO: HoleriteItemNatureza.DESCONTO,
            NaturezaEncargo.INFORMATIVO: HoleriteItemNatureza.INFORMATIVO,
        }[regra.natureza]
        if regra.natureza == NaturezaEncargo.INFORMATIVO:
            tipo = HoleriteItemTipo.INFORMATIVO
        elif regra.natureza == NaturezaEncargo.PROVENTO:
            tipo = HoleriteItemTipo.BENEFICIO_AUTOMATICO
        else:
            tipo = HoleriteItemTipo.ENCARGO_AUTOMATICO

        return HoleriteItem(
            team_id=context.team_id,
            holerite_id=context.holerite_id,
            funcionario_id=context.funcionario_id,
            tipo=tipo,
            origem="regra",
            codigo=regra.codigo,
            descricao=regra.nome,
            natureza=natureza,
            ordem=regra.prioridade,
            base=base,
            valor=valor,
            regra_encargo_id=regra.id,
            regra_grupo_id=regra.regra_grupo_id,
            snapshot_regra={
                "codigo": regra.codigo,
                "nome": regra.nome,
                "tipo_calculo": regra.tipo_calculo.value,
                "natureza": regra.natureza.value,
                "base_calculo": regra.base_calculo.value,
                "prioridade": regra.prioridade,
                "valor_fixo": str(regra.valor_fixo.amount) if regra.valor_fixo else None,
                "percentual": str(regra.percentual) if regra.percentual is not None else None,
                "tabela_progressiva_id": str(regra.tabela_progressiva_id) if regra.tabela_progressiva_id else None,
                "vigencia_inicio": regra.vigencia_inicio.isoformat() if regra.vigencia_inicio else None,
                "vigencia_fim": regra.vigencia_fim.isoformat() if regra.vigencia_fim else None,
            },
            snapshot_calculo=snapshot_calculo,
        )

    def _consolidar(self, itens: list[HoleriteItem]) -> FolhaCalculationResult:
        zero = Money(Decimal("0.00"))
        total_proventos = zero
        total_descontos = zero
        total_informativos = zero
        valor_bruto = zero

        for item in itens:
            if item.natureza == HoleriteItemNatureza.PROVENTO:
                total_proventos = total_proventos + item.valor
                valor_bruto = valor_bruto + item.valor
            elif item.natureza == HoleriteItemNatureza.DESCONTO:
                total_descontos = total_descontos + item.valor
                if item.tipo != HoleriteItemTipo.AJUSTE_MANUAL or item.codigo != "DESCONTO_MANUAL":
                    valor_bruto = valor_bruto - item.valor
            else:
                total_informativos = total_informativos + item.valor

        return FolhaCalculationResult(
            itens=itens,
            total_proventos=total_proventos,
            total_descontos=total_descontos,
            total_informativos=total_informativos,
            valor_bruto=valor_bruto,
            valor_liquido=total_proventos - total_descontos,
        )
