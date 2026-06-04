"""
Rotas públicas da obra — sem autenticação, somente leitura.

O acesso é controlado pelo próprio UUID da obra: conhecer o UUID é suficiente
para visualizar o painel do cliente (link público único por obra).

Dados retornados:
  - Título, status, data de entrega e descrição da obra
  - Kanban completo (itens + status + fotos de cada item)
  - Galeria de fotos da obra

Dados NUNCA retornados:
  - responsavel_id / team_id
  - valor, pagamentos, diárias
  - mural interno
  - qualquer dado administrativo
"""
import asyncio
from fastapi import APIRouter, HTTPException
from uuid import UUID

from app.http.schemas.obras import (
    PublicObraResponse, PublicItemView, PublicItemAttachmentView, PublicImageView,
    PublicRecebimentoAttachmentView, PublicRecebimentoView,
)
from app.http.dependencies.services import (
    ObraServiceDep, ItemServiceDep, ObraImageServiceDep,
    ItemAttachmentServiceDep, StorageProviderDep, RecebimentoServiceDep,
    FinanceiroServiceDep,
)
from app.domain.errors import DomainError
from app.infra.cache.client import get_redis
from app.infra.cache.keys import public_obra_key
from app.core.config import settings

router = APIRouter(prefix="/public", tags=["Public"])

_BUCKET = "engify"
_URL_TTL = 3600      # signed URLs válidas por 1 hora
_CACHE_TTL = 600     # cache Redis por 10 minutos (bem abaixo do TTL das URLs)
_RECEBIMENTOS_LIMIT = 1000


async def _sign(storage: StorageProviderDep, path: str) -> str:
    """Gera URL assinada para download. Retorna string vazia em caso de erro."""
    try:
        return await storage.get_signed_download_url(
            bucket=_BUCKET, path=path, expires_in=_URL_TTL
        )
    except Exception:
        return ""


@router.get("/obras/{obra_id}", response_model=PublicObraResponse)
async def get_obra_public(
    obra_id: UUID,
    svc: ObraServiceDep,
    item_svc: ItemServiceDep,
    image_svc: ObraImageServiceDep,
    att_svc: ItemAttachmentServiceDep,
    rec_svc: RecebimentoServiceDep,
    financeiro_svc: FinanceiroServiceDep,
    storage: StorageProviderDep,
):
    """
    Retorna a visão pública e somente leitura de uma obra.

    Não requer autenticação. O UUID da obra serve como token de acesso.
    URLs de imagens são assinadas com validade de 1 hora e cacheadas por 10 min.
    """
    redis = get_redis()
    cache_key = public_obra_key(obra_id)

    cached = await redis.get(cache_key)
    if cached:
        return PublicObraResponse.model_validate_json(cached)

    # Busca a obra sem filtro de team_id (acesso por UUID puro)
    try:
        obra = await svc.get_obra(obra_id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")

    # Queries independentes — executadas sequencialmente para evitar conflito de sessão
    items = await item_svc.list_items(obra_id)
    images = await image_svc.list_by_obra(obra_id)
    recebimentos = await rec_svc.list_entradas(
        obra.id, obra.team_id, page=1, limit=_RECEBIMENTOS_LIMIT
    )

    # Coleta attachments de todos os itens (sequencial — mesma sessão DB)
    item_attachments: dict[UUID, list] = {}
    for item in items:
        item_attachments[item.id] = await att_svc.list_by_item(item.id)

    recebimento_attachments: dict[UUID, list] = {}
    for recebimento in recebimentos:
        attachments = await financeiro_svc.get_attachments(recebimento.id)
        recebimento_attachments[recebimento.id] = [
            att for att in attachments if att.team_id == obra.team_id
        ]

    # Gera TODAS as URLs assinadas de forma concorrente (I/O externo ao Supabase)
    image_paths = [img.file_path for img in images]
    att_paths = [
        att.file_path
        for item in items
        for att in item_attachments[item.id]
    ]
    recebimento_att_paths = [
        att.file_path
        for recebimento in recebimentos
        for att in recebimento_attachments[recebimento.id]
    ]
    all_paths = image_paths + att_paths + recebimento_att_paths

    signed = await asyncio.gather(*[_sign(storage, p) for p in all_paths])
    url_map: dict[str, str] = dict(zip(all_paths, signed))

    # Monta a resposta pública — sem nenhum campo sensível
    public_images = [
        PublicImageView(
            id=img.id,
            file_name=img.file_name,
            download_url=url_map.get(img.file_path, ""),
        )
        for img in images
    ]

    public_items = [
        PublicItemView(
            id=item.id,
            title=item.title,
            status=item.status,
            descricao=item.description,
            responsavel_nome=item.responsavel_nome,
            attachments=[
                PublicItemAttachmentView(
                    id=att.id,
                    file_name=att.file_name,
                    download_url=url_map.get(att.file_path, ""),
                    content_type=att.content_type,
                )
                for att in item_attachments[item.id]
            ],
        )
        for item in items
    ]

    public_recebimentos = [
        PublicRecebimentoView(
            id=recebimento.id,
            title=recebimento.title,
            data_movimentacao=recebimento.data_movimentacao,
            attachments=[
                PublicRecebimentoAttachmentView(
                    id=att.id,
                    file_name=att.file_name,
                    download_url=url_map.get(att.file_path, ""),
                    content_type=att.content_type,
                )
                for att in recebimento_attachments[recebimento.id]
            ],
        )
        for recebimento in recebimentos
    ]

    response = PublicObraResponse(
        id=obra.id,
        title=obra.title,
        description=obra.description,
        status=obra.status,
        data_entrega=obra.data_entrega,
        items=public_items,
        images=public_images,
        recebimentos=public_recebimentos,
    )

    await redis.set(cache_key, response.model_dump_json(), ex=_CACHE_TTL)
    return response
