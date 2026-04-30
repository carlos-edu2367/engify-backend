from uuid import UUID
from decimal import Decimal
from app.application.providers.repo.financeiro_repo import MovimentacaoRepository
from app.application.dtos.financeiro import FluxoCaixaDTO, FluxoCaixaItemDTO, FluxoCaixaResumoDTO


class FinanceiroFluxoCaixaService:
    def __init__(self, mov_repo: MovimentacaoRepository):
        self.mov_repo = mov_repo

    async def get_fluxo_caixa(self, team_id: UUID, range_str: str) -> FluxoCaixaDTO:
        # Converte range para meses
        months_map = {"6m": 6, "12m": 12, "24m": 24}
        months = months_map.get(range_str, 6)

        raw_data = await self.mov_repo.get_fluxo_caixa(team_id, months)

        dados = []
        total_entradas_periodo = Decimal("0")
        total_saidas_periodo = Decimal("0")

        for row in raw_data:
            entradas = Decimal(str(row["total_entradas"] or 0))
            saidas = Decimal(str(row["total_saidas"] or 0))
            saldo = entradas - saidas
            
            total_entradas_periodo += entradas
            total_saidas_periodo += saidas

            dados.append(
                FluxoCaixaItemDTO(
                    mes=row["mes"],
                    total_entradas=entradas,
                    total_saidas=saidas,
                    saldo=saldo,
                )
            )

        resumo = FluxoCaixaResumoDTO(
            total_entradas=total_entradas_periodo,
            total_saidas=total_saidas_periodo,
            saldo_total=total_entradas_periodo - total_saidas_periodo,
        )

        return FluxoCaixaDTO(
            periodo=range_str,
            dados=dados,
            resumo=resumo,
        )
