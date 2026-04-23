"""
Todos os cache keys são prefixados com team_id para garantir
isolamento entre tenants. Nunca use uma key sem o prefixo de tenant.

Formato: {team_id}:{recurso}:{params...}
TTL padrão: 60s (configurável por recurso)
"""
from uuid import UUID


def team_key(team_id: UUID) -> str:
    """Dados do time em si (plano, expiração)."""
    return f"{team_id}:team"


def obras_list_key(team_id: UUID, page: int, limit: int, status: str = "all") -> str:
    return f"{team_id}:obras:list:{page}:{limit}:{status}"


def obra_detail_key(team_id: UUID, obra_id: UUID) -> str:
    return f"{team_id}:obras:{obra_id}"


def items_list_key(team_id: UUID, obra_id: UUID) -> str:
    return f"{team_id}:obras:{obra_id}:items"


def diaristas_list_key(team_id: UUID, page: int, limit: int) -> str:
    return f"{team_id}:diaristas:list:{page}:{limit}"


def diarias_list_key(team_id: UUID, start: str, end: str, page: int, limit: int,
                     obra_id: UUID | None = None) -> str:
    base = f"{team_id}:diarias:{start}:{end}:{page}:{limit}"
    if obra_id is not None:
        base += f":{obra_id}"
    return base


import hashlib
import json

def movimentacoes_list_key(team_id: UUID, page: int, limit: int, filters_dict: dict | None = None) -> str:
    base = f"{team_id}:movimentacoes:list:{page}:{limit}"
    if filters_dict:
        sorted_filters = {k: str(v) for k, v in sorted(filters_dict.items()) if v is not None}
        if sorted_filters:
            hashed = hashlib.md5(json.dumps(sorted_filters).encode()).hexdigest()
            base += f":{hashed}"
    return base


def pagamentos_list_key(team_id: UUID, page: int, limit: int, filters_dict: dict | None = None) -> str:
    base = f"{team_id}:pagamentos:list:{page}:{limit}"
    if filters_dict:
        sorted_filters = {k: str(v) for k, v in sorted(filters_dict.items()) if v is not None}
        if sorted_filters:
            hashed = hashlib.md5(json.dumps(sorted_filters).encode()).hexdigest()
            base += f":{hashed}"
    return base


def users_list_key(team_id: UUID) -> str:
    return f"{team_id}:users:list"


# Padrões para invalidação (SCAN + DEL)
def team_pattern(team_id: UUID) -> str:
    """Invalida TUDO de um tenant."""
    return f"{team_id}:*"


def obras_pattern(team_id: UUID) -> str:
    return f"{team_id}:obras:*"


def items_pattern(team_id: UUID, obra_id: UUID) -> str:
    return f"{team_id}:obras:{obra_id}:items*"


def diaristas_pattern(team_id: UUID) -> str:
    return f"{team_id}:diaristas:*"


def diarias_pattern(team_id: UUID) -> str:
    return f"{team_id}:diarias:*"


def movimentacoes_pattern(team_id: UUID) -> str:
    return f"{team_id}:movimentacoes:*"


def pagamentos_pattern(team_id: UUID) -> str:
    return f"{team_id}:pagamentos:*"


def revoked_token_key(jti: str) -> str:
    """Key de um refresh token revogado (logout). TTL = validade restante do token."""
    return f"revoked:{jti}"


def mural_list_key(team_id: UUID, obra_id: UUID, page: int, limit: int) -> str:
    return f"{team_id}:obras:{obra_id}:mural:{page}:{limit}"


def mural_pattern(team_id: UUID, obra_id: UUID) -> str:
    """Invalida todo o cache do mural de uma obra."""
    return f"{team_id}:obras:{obra_id}:mural*"


def item_attachments_key(team_id: UUID, item_id: UUID) -> str:
    return f"{team_id}:items:{item_id}:attachments"


def item_attachments_pattern(team_id: UUID, item_id: UUID) -> str:
    return f"{team_id}:items:{item_id}:attachments*"


def obra_cliente_key(team_id: UUID, obra_id: UUID) -> str:
    return f"{team_id}:obras:{obra_id}:cliente"


def movimentacao_attachments_key(team_id: UUID, mov_id: UUID) -> str:
    return f"{team_id}:movimentacoes:{mov_id}:attachments"


def movimentacao_attachments_pattern(team_id: UUID, mov_id: UUID) -> str:
    return f"{team_id}:movimentacoes:{mov_id}:attachments*"


def movimentacao_delete_lock_key(team_id: UUID, mov_id: UUID) -> str:
    return f"{team_id}:movimentacoes:{mov_id}:delete:lock"


def movimentacao_deleted_tombstone_key(team_id: UUID, mov_id: UUID) -> str:
    return f"{team_id}:movimentacoes:{mov_id}:delete:done"


def mural_post_attachments_key(team_id: UUID, obra_id: UUID, post_id: UUID) -> str:
    # Encaixado dentro de mural_pattern — invalidado por _invalidate_mural_cache.
    return f"{team_id}:obras:{obra_id}:mural:{post_id}:attachments"


def mural_obra_attachments_key(team_id: UUID, obra_id: UUID) -> str:
    # Encaixado dentro de mural_pattern — invalidado por _invalidate_mural_cache.
    return f"{team_id}:obras:{obra_id}:mural:attachments"


def public_obra_key(obra_id: UUID) -> str:
    """Cache da visão pública da obra (sem tenant prefix — acesso sem autenticação)."""
    return f"public:obra:{obra_id}"


def categorias_obra_list_key(team_id: UUID, page: int, limit: int) -> str:
    return f"{team_id}:categorias_obra:list:{page}:{limit}"


def categoria_obra_detail_key(team_id: UUID, categoria_id: UUID) -> str:
    return f"{team_id}:categorias_obra:{categoria_id}"


def categorias_obra_pattern(team_id: UUID) -> str:
    return f"{team_id}:categorias_obra:*"


def entradas_obra_key(team_id: UUID, obra_id: UUID, page: int, limit: int) -> str:
    return f"{team_id}:obras:{obra_id}:entradas:{page}:{limit}"


def entradas_obra_pattern(team_id: UUID, obra_id: UUID) -> str:
    """Invalida cache de entradas de uma obra específica."""
    return f"{team_id}:obras:{obra_id}:entradas*"


def notif_list_key(user_id: UUID, team_id: UUID, page: int, limit: int) -> str:
    return f"{team_id}:notif:{user_id}:list:{page}:{limit}"


def notif_count_key(user_id: UUID, team_id: UUID) -> str:
    return f"{team_id}:notif:{user_id}:count"


def notif_pattern(user_id: UUID, team_id: UUID) -> str:
    return f"{team_id}:notif:{user_id}:*"
