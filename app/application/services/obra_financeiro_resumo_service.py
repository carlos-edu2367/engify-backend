from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.application.dtos.obra_financeiro import CustoPorClasseDTO, ObraFinanceiroResumoDTO
from app.application.providers.repo.financeiro_repo import (
    MovimentacaoRepository, PagamentoAgendadoRepository,
)
from app.application.providers.repo.obra_repo import ObraRepository
from app.domain.entities.financeiro import MovClass

TWO_PLACES = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class ObraFinanceiroResumoService:
    def __init__(
        self,
        obra_repo: ObraRepository,
        mov_repo: MovimentacaoRepository,
        pagamento_repo: PagamentoAgendadoRepository,
    ):
        self.obra_repo = obra_repo
        self.mov_repo = mov_repo
        self.pagamento_repo = pagamento_repo

    async def get_resumo(self, obra_id: UUID, team_id: UUID) -> ObraFinanceiroResumoDTO:
        obra = await self.obra_repo.get_by_id(obra_id, team_id)
        resumo_rows = await self.mov_repo.get_resumo_obra(obra_id, team_id)
        comprometido_rows = await self.pagamento_repo.get_comprometido_obra(obra_id, team_id)

        entradas = Decimal("0")
        saidas = Decimal("0")
        qtd_movimentacoes = 0
        realizado_por_classe: dict[str, Decimal] = {}

        for row in resumo_rows:
            total = Decimal(str(row["total"] or 0))
            qtd_movimentacoes += row["qtd"] or 0
            if row["type"] == "entrada":
                entradas += total
            else:
                saidas += total
                realizado_por_classe[row["classe"]] = (
                    realizado_por_classe.get(row["classe"], Decimal("0")) + total
                )

        comprometido = Decimal("0")
        qtd_pagamentos_aguardando = 0
        comprometido_por_classe: dict[str, Decimal] = {}

        for row in comprometido_rows:
            total = Decimal(str(row["total"] or 0))
            qtd_pagamentos_aguardando += row["qtd"] or 0
            comprometido += total
            comprometido_por_classe[row["classe"]] = (
                comprometido_por_classe.get(row["classe"], Decimal("0")) + total
            )

        resultado_realizado = entradas - saidas
        custo_previsto = saidas + comprometido

        contrato = _q(obra.valor.amount) if obra.valor is not None else None
        margem_projetada = _q(contrato - custo_previsto) if contrato is not None else None
        margem_projetada_pct = (
            _q((margem_projetada / contrato) * Decimal("100"))
            if contrato not in (None, Decimal("0"))
            else None
        )
        a_receber = _q(contrato - entradas) if contrato is not None else None

        classes = set(realizado_por_classe) | set(comprometido_por_classe)
        custos_por_classe = [
            CustoPorClasseDTO(
                classe=MovClass(classe),
                realizado=_q(realizado_por_classe.get(classe, Decimal("0"))),
                comprometido=_q(comprometido_por_classe.get(classe, Decimal("0"))),
            )
            for classe in classes
        ]
        custos_por_classe.sort(key=lambda c: c.realizado + c.comprometido, reverse=True)

        return ObraFinanceiroResumoDTO(
            obra_id=obra_id,
            contrato=contrato,
            entradas=_q(entradas),
            saidas=_q(saidas),
            comprometido=_q(comprometido),
            resultado_realizado=_q(resultado_realizado),
            custo_previsto=_q(custo_previsto),
            margem_projetada=margem_projetada,
            margem_projetada_pct=margem_projetada_pct,
            a_receber=a_receber,
            total_recebido_obra=_q(obra.total_recebido),
            custos_por_classe=custos_por_classe,
            qtd_movimentacoes=qtd_movimentacoes,
            qtd_pagamentos_aguardando=qtd_pagamentos_aguardando,
        )
