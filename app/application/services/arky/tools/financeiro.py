"""Read-only and prepare tools for Financeiro module. Sensitive data is minimized.

Pix completo (``pix_copy_and_past``) e o código do recebedor (``payment_cod``)
NUNCA são devolvidos ao modelo — apenas a existência do código é sinalizada.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.application.services.arky.tools.context import ArkyToolContext
from app.domain.entities.financeiro import MovClass
from app.domain.errors import DomainError

logger = logging.getLogger(__name__)

_VALID_RANGES = {"6m", "12m", "24m"}

_MAX_PREVIEW_ITENS = 20
_VALID_CLASSES = {c.value for c in MovClass}


def _pagamento_summary(p, *, reference: datetime | None = None) -> dict:
    """Resumo seguro de um pagamento (sem Pix/payment_cod)."""
    data_agendada = getattr(p, "data_agendada", None)
    item: dict = {
        "id": str(p.id),
        "title": p.title,
        "valor": float(p.valor.amount),
        "classe": p.classe.value,
        "status": p.status.value,
        "data_agendada": data_agendada.isoformat() if data_agendada else None,
        "tem_codigo_pagamento": bool(getattr(p, "payment_cod", None)),
        "created_by_name": getattr(p, "created_by_name", None),
        "created_by_engineer": bool(getattr(p, "created_by_engineer", False)),
    }
    pay_date = getattr(p, "payment_date", None)
    if pay_date:
        item["payment_date"] = pay_date.isoformat()
    if reference and data_agendada and p.status.value == "aguardando":
        dias = (reference - data_agendada).days
        if dias > 0:
            item["dias_em_atraso"] = dias
    return item


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


async def financeiro_pagamentos_overview(params: dict, ctx: ArkyToolContext) -> dict:
    """Pagamentos atrasados e resumo. Engenheiro vê apenas os próprios."""
    try:
        limit = min(int(params.get("limit", 15)), 30)
    except (TypeError, ValueError):
        limit = 15

    now = datetime.now(timezone.utc)
    try:
        atrasados = await ctx.financeiro_service.list_pagamentos_overdue(
            team_id=ctx.team_id, actor_user=ctx.user, limit=limit, reference=now,
        )
    except Exception as e:
        logger.warning("Erro ao buscar pagamentos atrasados: %s", e)
        return {"error": "Não foi possível buscar os pagamentos"}

    itens = [_pagamento_summary(p, reference=now) for p in atrasados]
    total_atrasado = round(sum(float(p.valor.amount) for p in atrasados), 2)
    return {
        "total_atrasados": len(itens),
        "valor_total_atrasado": total_atrasado,
        "atrasados": itens,
    }


async def financeiro_buscar_pagamentos(params: dict, ctx: ArkyToolContext) -> dict:
    """Busca pagamentos por nome/texto (ex.: último pagamento para a pessoa X).

    Engenheiro vê apenas os próprios. Não expõe Pix nem código do recebedor."""
    query = (params.get("query") or "").strip()
    if len(query) < 2:
        return {"error": "Informe ao menos 2 caracteres para buscar"}

    try:
        limit = min(int(params.get("limit", 10)), 20)
    except (TypeError, ValueError):
        limit = 10

    now = datetime.now(timezone.utc)
    try:
        pagamentos = await ctx.financeiro_service.search_pagamentos(
            team_id=ctx.team_id, query=query[:120], actor_user=ctx.user, limit=limit,
        )
    except Exception as e:
        logger.warning("Erro ao buscar pagamentos: %s", e)
        return {"error": "Não foi possível buscar os pagamentos"}

    itens = [_pagamento_summary(p, reference=now) for p in pagamentos]
    ultimo_pago = next(
        (i for i in itens if i["status"] == "pago"), None
    )
    return {
        "query": query[:120],
        "total": len(itens),
        "pagamentos": itens,
        "ultimo_pagamento_efetuado": ultimo_pago,
    }


def _parse_data_agendada(value) -> datetime:
    """Converte string ISO em datetime tz-aware; default = agora (hoje)."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def _validate_pagamento_item(item: dict, ctx: ArkyToolContext) -> dict:
    """Valida e normaliza um item de pagamento. Levanta ValueError com mensagem."""
    if not isinstance(item, dict):
        raise ValueError("Item de pagamento inválido")

    title = (item.get("title") or "").strip()
    if not title:
        raise ValueError("title é obrigatório em cada pagamento")

    classe = (item.get("classe") or "").strip().lower()
    if classe not in _VALID_CLASSES:
        raise ValueError(
            f"classe inválida '{classe}'. Use uma de: {', '.join(sorted(_VALID_CLASSES))}"
        )

    try:
        valor = Decimal(str(item.get("valor")))
    except (TypeError, ValueError, InvalidOperation):
        raise ValueError(f"valor inválido no pagamento '{title}'")
    if valor <= 0:
        raise ValueError(f"valor deve ser positivo no pagamento '{title}'")

    payment_cod = item.get("payment_cod")
    payment_cod = payment_cod.strip() if isinstance(payment_cod, str) else None

    normalized: dict = {
        "title": title[:200],
        "details": (item.get("details") or "").strip()[:1000],
        "valor": str(valor),
        "classe": classe,
        "data_agendada": _parse_data_agendada(item.get("data_agendada")).isoformat(),
        "payment_cod": payment_cod or None,
    }

    obra_id = item.get("obra_id")
    if obra_id:
        try:
            obra_uuid = UUID(str(obra_id))
        except (TypeError, ValueError):
            raise ValueError(f"obra_id inválido no pagamento '{title}'")
        try:
            obra = await ctx.obra_service.get_obra(obra_uuid, ctx.team_id)
        except DomainError:
            raise ValueError(f"Obra não encontrada para o pagamento '{title}'")
        normalized["obra_id"] = str(obra_uuid)
        normalized["obra_title"] = obra.title

    diarist_id = item.get("diarist_id")
    if diarist_id:
        try:
            diarist_uuid = UUID(str(diarist_id))
        except (TypeError, ValueError):
            raise ValueError(f"diarist_id inválido no pagamento '{title}'")
        try:
            diarist = await ctx.diarist_service.get_diarist(diarist_uuid, ctx.team_id)
        except DomainError:
            raise ValueError(f"Diarista não encontrado para o pagamento '{title}'")
        normalized["diarist_id"] = str(diarist_uuid)
        normalized["diarist_nome"] = diarist.nome

    return normalized


async def financeiro_prepare_pagamentos(params: dict, ctx: ArkyToolContext) -> dict:
    """Prepara uma LISTA de pagamentos agendados para confirmação humana.

    NÃO cria nada. Os pagamentos só são criados quando o usuário confirma a
    prévia — momento em que o backend valida tudo novamente e carimba a autoria
    (criado por / criado por engenheiro) a partir do token autenticado.
    """
    itens_raw = params.get("pagamentos")
    if not isinstance(itens_raw, list) or not itens_raw:
        return {"error": "Envie uma lista 'pagamentos' com ao menos um item"}
    if len(itens_raw) > _MAX_PREVIEW_ITENS:
        return {"error": f"Máximo de {_MAX_PREVIEW_ITENS} pagamentos por sugestão"}

    # Engenheiro precisa de código de pagamento em todos os itens (regra do backend).
    from app.domain.entities.user import Roles
    is_engineer = ctx.user.role == Roles.ENGENHEIRO

    itens: list[dict] = []
    for raw in itens_raw:
        try:
            normalized = await _validate_pagamento_item(raw, ctx)
        except ValueError as e:
            return {"error": str(e)}
        if is_engineer and not normalized.get("payment_cod"):
            return {
                "error": (
                    f"Como engenheiro, o código de pagamento (Pix/código de barras) "
                    f"é obrigatório no pagamento '{normalized['title']}'"
                )
            }
        itens.append(normalized)

    total = round(sum(float(i["valor"]) for i in itens), 2)

    preview_payload = {
        "itens": itens,
        "team_id": str(ctx.team_id),
        "user_id": str(ctx.user.id),
    }

    resumo = (
        f"Agendar {len(itens)} pagamento(s) — total R$ {total:.2f}".replace(".", ",")
    )

    from app.domain.entities.arky import ArkyActionPreview
    preview = ArkyActionPreview(
        team_id=ctx.team_id,
        user_id=ctx.user.id,
        conversation_id=ctx.team_id,  # placeholder; orquestrador corrige
        action_type="prepare_create_pagamentos",
        payload=preview_payload,
        summary=resumo,
        risk_level="preparacao",
    )

    saved = await ctx.arky_preview_repo.save(preview)
    await ctx.uow.commit()

    return {
        "action_preview_id": str(saved.id),
        "action_type": "prepare_create_pagamentos",
        "summary": saved.summary,
        "risk_level": saved.risk_level,
        "requires_confirmation": True,
        "preview": {
            "total": total,
            "quantidade": len(itens),
            "itens": [
                {
                    "title": i["title"],
                    "valor": float(i["valor"]),
                    "classe": i["classe"],
                    "data_agendada": i["data_agendada"],
                    "tem_codigo_pagamento": bool(i.get("payment_cod")),
                    "payment_cod": i.get("payment_cod"),
                    "obra_title": i.get("obra_title"),
                    "diarist_nome": i.get("diarist_nome"),
                }
                for i in itens
            ],
        },
        "expires_in_minutes": 15,
    }
