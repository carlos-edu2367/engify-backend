from uuid import UUID

from app.infra.cache.keys import obra_financeiro_resumo_pattern


async def invalidate_obra_financeiro_resumo(redis, team_id: UUID) -> None:
    """Invalida o resumo financeiro de todas as obras do time.

    Invalidar o time inteiro em vez de uma obra evita propagar obra_id ate
    pontos que hoje nao o tem (baixa em lote). Com TTL de 5 min o custo e
    irrelevante."""
    async for key in redis.scan_iter(match=obra_financeiro_resumo_pattern(team_id), count=100):
        await redis.delete(key)
