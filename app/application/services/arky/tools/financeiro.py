"""Read-only tools for Financeiro module. Sensitive data is minimized."""
from __future__ import annotations

import logging

from app.application.services.arky.tools.context import ArkyToolContext

logger = logging.getLogger(__name__)

_VALID_RANGES = {"6m", "12m", "24m"}


async def financeiro_get_fluxo_caixa(params: dict, ctx: ArkyToolContext) -> dict:
    # Map mes/ano to nearest range_str for compatibility with current service
    range_str = "6m"  # default: last 6 months

    try:
        fluxo = await ctx.financeiro_fluxo_service.get_fluxo_caixa(
            team_id=ctx.team_id,
            range_str=range_str,
        )
    except Exception as e:
        logger.warning("Erro ao buscar fluxo de caixa: %s", e)
        return {"error": "Não foi possível buscar o fluxo de caixa"}

    if not fluxo:
        return {"error": "Dados de fluxo de caixa indisponíveis"}

    resumo = getattr(fluxo, "resumo", None)
    dados = getattr(fluxo, "dados", [])

    result: dict = {
        "periodo": getattr(fluxo, "periodo", range_str),
        "meses_disponiveis": len(dados),
    }

    if resumo:
        result["total_entradas"] = float(getattr(resumo, "total_entradas", 0))
        result["total_saidas"] = float(getattr(resumo, "total_saidas", 0))
        result["saldo_total"] = float(getattr(resumo, "saldo_total", 0))

    # Include last 3 months summary (no individual transactions, no Pix)
    recent = []
    for item in (dados or [])[-3:]:
        recent.append({
            "mes": getattr(item, "mes", None),
            "total_entradas": float(getattr(item, "total_entradas", 0)),
            "total_saidas": float(getattr(item, "total_saidas", 0)),
            "saldo": float(getattr(item, "saldo", 0)),
        })
    result["ultimos_meses"] = recent

    return result
