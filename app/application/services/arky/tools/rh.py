"""Read-only RH tools. CPF, salários e documentos são mascarados/omitidos."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.application.services.arky.tools.context import ArkyToolContext

logger = logging.getLogger(__name__)


async def rh_get_me_resumo(params: dict, ctx: ArkyToolContext) -> dict:
    """Resumo RH do próprio funcionário. Somente para role FUNCIONARIO."""
    try:
        resumo = await ctx.rh_dashboard_service.obter_meu_resumo(
            current_user=ctx.user,
        )
    except Exception as e:
        logger.warning("Erro ao buscar resumo RH do funcionário: %s", e)
        return {"error": "Não foi possível buscar o resumo RH"}

    return _sanitize_me_resumo(resumo)


async def rh_get_dashboard(params: dict, ctx: ArkyToolContext) -> dict:
    """Dashboard RH do time. Somente para roles admin/financeiro."""
    now = datetime.now(timezone.utc)
    mes = int(params.get("mes", now.month))
    ano = int(params.get("ano", now.year))

    if not (1 <= mes <= 12):
        return {"error": "Mês inválido (1-12)"}

    try:
        dashboard = await ctx.rh_dashboard_service.obter_dashboard(
            current_user=ctx.user,
            mes=mes,
            ano=ano,
        )
    except Exception as e:
        logger.warning("Erro ao buscar dashboard RH: %s", e)
        return {"error": "Não foi possível buscar o dashboard RH"}

    return _sanitize_dashboard(dashboard)


def _sanitize_dashboard(dashboard) -> dict:
    """Only aggregate/count fields — no CPF, salary, geolocalization, documents."""
    if dashboard is None:
        return {"error": "Dashboard indisponível"}

    result: dict = {}
    safe_fields = [
        "total_funcionarios",
        "funcionarios_ativos",
        "total_ajustes_pendentes",
        "total_ferias_pendentes",
        "total_atestados_pendentes",
        "total_pontos_hoje",
        "folha_status",
        "competencia",
    ]
    for f in safe_fields:
        value = getattr(dashboard, f, None)
        if value is not None:
            result[f] = value

    return result or {"info": "Dashboard sem dados disponíveis para este período"}


def _sanitize_me_resumo(resumo) -> dict:
    """Only safe personal fields — no salary, no document URLs."""
    if resumo is None:
        return {"error": "Resumo indisponível"}

    result: dict = {}
    safe_fields = [
        "nome",
        "cargo",
        "ajustes_pendentes",
        "ferias_pendentes",
        "atestados_pendentes",
        "ultimo_ponto",
        "vinculo_ativo",
    ]
    for f in safe_fields:
        value = getattr(resumo, f, None)
        if value is not None and not _is_sensitive(f, value):
            result[f] = str(value) if not isinstance(value, (int, float, bool)) else value

    return result or {"info": "Nenhum dado disponível"}


def _is_sensitive(key: str, value) -> bool:
    sensitive_keys = {"cpf", "pix", "salario", "salary", "latitude", "longitude"}
    return key.lower() in sensitive_keys
