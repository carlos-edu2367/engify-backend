from fastapi import APIRouter, HTTPException
from uuid import UUID, uuid4

from app.http.schemas.storage import (
    UploadUrlRequest, UploadUrlResponse,
    DownloadUrlRequest, DownloadUrlResponse,
    ALLOWED_UPLOAD_TYPES,
)
from app.http.dependencies.auth import CurrentUser, EngineerUser, ManagerUser
from app.http.dependencies.services import (
    StorageProviderDep, ObraServiceDep, ItemServiceDep,
    FinanceiroServiceDep, MuralServiceDep,
)
from app.application.providers.utility.storage_provider import DirectUploadRequest
from app.core.config import settings
from app.domain.errors import DomainError

router = APIRouter(prefix="/storage", tags=["Storage"])

BUCKET = "engify"

# Extensões permitidas por content-type
_ALLOWED_EXTENSIONS = {
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
    "image/webp": {"webp"},
    "application/pdf": {"pdf"},
}


def _build_path(resource_type: str, resource_id, file_name: str, content_type: str) -> str:
    """
    Constrói o path com prefixo no bucket.
    Formato: {prefix}/{resource_id}/{uuid}.{ext}
    A extensão é derivada do content_type validado, não do file_name fornecido pelo cliente.
    """
    allowed_exts = _ALLOWED_EXTENSIONS.get(content_type, set())
    # Tenta preservar a extensão original se ela for permitida; caso contrário usa a primeira da lista
    original_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    ext = original_ext if original_ext in allowed_exts else next(iter(sorted(allowed_exts)), "bin")
    return f"{resource_type}/{resource_id}/{uuid4()}.{ext}"


async def _validate_resource_ownership(
    resource_type: str,
    resource_id: UUID,
    team_id: UUID,
    obra_svc: ObraServiceDep,
    item_svc: ItemServiceDep,
    fin_svc: FinanceiroServiceDep,
    mural_svc: MuralServiceDep,
) -> None:
    """Verifica que o resource_id pertence ao team_id. Levanta 404 se não pertencer."""
    try:
        if resource_type == "obra":
            await obra_svc.get_obra(resource_id, team_id)
        elif resource_type == "item":
            await item_svc.get_item(resource_id, team_id)
        elif resource_type == "financeiro":
            await fin_svc.get_pagamento(resource_id, team_id)
        elif resource_type == "mural":
            await mural_svc.get_post(resource_id, team_id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")


def _parse_resource_from_path(path: str) -> tuple[str, UUID]:
    """
    Extrai resource_type e resource_id do path de storage.
    Formato esperado: '{resource_type}/{resource_id}/{filename}'
    Levanta 422 se o formato for inválido.
    """
    parts = path.split("/")
    if len(parts) != 3:
        raise HTTPException(status_code=422, detail="Path inválido")
    resource_type = parts[0]
    try:
        resource_id = UUID(parts[1])
    except ValueError:
        raise HTTPException(status_code=422, detail="Path inválido")
    return resource_type, resource_id


@router.post("/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    body: UploadUrlRequest,
    user: ManagerUser,
    storage: StorageProviderDep,
    obra_svc: ObraServiceDep,
    item_svc: ItemServiceDep,
    fin_svc: FinanceiroServiceDep,
    mural_svc: MuralServiceDep,
):
    """
    Gera presigned URL para upload direto pelo frontend (PUT).
    O frontend envia o arquivo diretamente para o Supabase Storage.
    O backend nunca recebe o binário.

    Tipos permitidos:
    - obra: image/jpeg, image/png, image/webp
    - item: image/jpeg, image/png, image/webp
    - financeiro: image/jpeg, image/png, image/webp, application/pdf
    - mural: image/jpeg, image/png, image/webp, application/pdf

    Restrito a ADMIN, ENG e FINANCEIRO.
    """
    allowed = ALLOWED_UPLOAD_TYPES.get(body.resource_type, set())
    if body.content_type not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo '{body.content_type}' não permitido para '{body.resource_type}'. "
                   f"Permitidos: {sorted(allowed)}",
        )

    await _validate_resource_ownership(
        body.resource_type, body.resource_id, user.team.id,
        obra_svc, item_svc, fin_svc, mural_svc,
    )

    path = _build_path(body.resource_type, body.resource_id, body.file_name, body.content_type)
    req = DirectUploadRequest(
        bucket=BUCKET,
        path=path,
        content_type=body.content_type,
        expires_in=settings.storage_upload_expires_in,
    )
    data = await storage.create_direct_upload(req)
    return UploadUrlResponse(
        upload_url=data.upload_url,
        path=data.path,
        expires_in=settings.storage_upload_expires_in,
    )


@router.post("/download-url", response_model=DownloadUrlResponse)
async def get_download_url(
    body: DownloadUrlRequest,
    user: CurrentUser,
    storage: StorageProviderDep,
    obra_svc: ObraServiceDep,
    item_svc: ItemServiceDep,
    fin_svc: FinanceiroServiceDep,
    mural_svc: MuralServiceDep,
):
    """
    Gera presigned URL para download de arquivo.
    Valida que o recurso referenciado no path pertence ao time do usuário autenticado.
    """
    # Rejeita sequências de path traversal antes de qualquer outra validação
    if ".." in body.path or "//" in body.path or body.path.startswith("/"):
        raise HTTPException(status_code=422, detail="Path inválido")

    valid_prefixes = ("obra/", "item/", "financeiro/", "mural/")
    if not any(body.path.startswith(p) for p in valid_prefixes):
        raise HTTPException(status_code=422, detail="Path inválido")

    resource_type, resource_id = _parse_resource_from_path(body.path)

    await _validate_resource_ownership(
        resource_type, resource_id, user.team.id,
        obra_svc, item_svc, fin_svc, mural_svc,
    )

    url = await storage.get_signed_download_url(
        bucket=BUCKET,
        path=body.path,
        expires_in=settings.storage_download_expires_in,
    )
    return DownloadUrlResponse(
        download_url=url,
        expires_in=settings.storage_download_expires_in,
    )
