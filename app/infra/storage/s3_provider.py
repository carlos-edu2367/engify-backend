import urllib.parse

import httpx

from app.application.providers.utility.storage_provider import (
    StorageProvider, DirectUploadRequest, DirectUploadData, StoredFileMetadata
)
from app.core.config import settings


class S3StorageProvider(StorageProvider):
    """
    Implementação de StorageProvider usando Supabase Storage REST API.

    Bucket único configurado via STORAGE_BUCKET_NAME (padrão: "engify").
    Prefixos de path para organização:
      - "obra/{obra_id}/{uuid}.ext"
      - "item/{item_id}/{uuid}.ext"
      - "financeiro/{pag_id}/{uuid}.ext"

    Upload é feito DIRETAMENTE pelo frontend usando presigned URL (PUT).
    O backend nunca recebe o binário do arquivo.
    """

    def __init__(self) -> None:
        self._base_url = settings.storage_url.rstrip("/")
        self._key = settings.storage_key
        self._bucket = settings.storage_bucket_name
        self._headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
        }

    async def create_direct_upload(self, request: DirectUploadRequest) -> DirectUploadData:
        """
        Gera presigned URL PUT para upload direto do frontend via Supabase Storage.
        Endpoint: POST /storage/v1/object/upload/sign/{bucket}/{path}
        O frontend usa PUT nessa URL com o binário do arquivo.
        """
        path_encoded = urllib.parse.quote(request.path, safe="/")
        url = f"{self._base_url}/storage/v1/object/upload/sign/{self._bucket}/{path_encoded}"

        async with httpx.AsyncClient(headers=self._headers, timeout=30.0) as client:
            response = await client.post(url, json={"upsert": True})

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Erro ao gerar URL de upload: HTTP {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        signed_path = data.get("url") or data.get("signedURL") or data.get("signedUrl")
        if not signed_path:
            raise RuntimeError(f"URL de upload não retornada pelo Supabase: {data}")

        upload_url = (
            signed_path
            if signed_path.startswith("http")
            else f"{self._base_url}/{signed_path.lstrip('/')}"
        )

        return DirectUploadData(
            upload_url=upload_url,
            path=request.path,
            headers={"Content-Type": request.content_type},
        )

    async def get_signed_download_url(
        self, bucket: str, path: str, expires_in: int = 3600
    ) -> str:
        """
        Gera URL assinada para download via Supabase Storage.
        Endpoint: POST /storage/v1/object/sign/{bucket}/{path}
        """
        path_encoded = urllib.parse.quote(path, safe="/")
        url = f"{self._base_url}/storage/v1/object/sign/{self._bucket}/{path_encoded}"

        async with httpx.AsyncClient(headers=self._headers, timeout=30.0) as client:
            response = await client.post(url, json={"expiresIn": expires_in})

        if response.status_code != 200:
            raise RuntimeError(
                f"Erro ao gerar URL de download: HTTP {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        signed_path = data.get("signedURL") or data.get("signedUrl") or data.get("url")
        if not signed_path:
            raise RuntimeError(f"URL assinada não retornada pelo Supabase: {data}")

        if signed_path.startswith("http"):
            return signed_path

        if not signed_path.startswith("/storage/v1"):
            signed_path = f"/storage/v1/{signed_path.lstrip('/')}"

        return f"{self._base_url}/{signed_path.lstrip('/')}"

    async def get_file_metadata(self, bucket: str, path: str) -> StoredFileMetadata:
        """
        Busca metadados do arquivo via HEAD.
        Endpoint: HEAD /storage/v1/object/{bucket}/{path}
        """
        path_encoded = urllib.parse.quote(path, safe="/")
        url = f"{self._base_url}/storage/v1/object/{self._bucket}/{path_encoded}"

        async with httpx.AsyncClient(headers=self._headers, timeout=15.0) as client:
            response = await client.head(url)

        if response.status_code == 404:
            return StoredFileMetadata(path=path, size=0, content_type=None, exists=False)

        if response.status_code not in (200, 206):
            raise RuntimeError(
                f"Erro ao buscar metadados: HTTP {response.status_code}"
            )

        content_length = int(response.headers.get("content-length", 0))
        content_type = response.headers.get("content-type")
        return StoredFileMetadata(
            path=path,
            size=content_length,
            content_type=content_type,
            exists=True,
        )

    async def upload_bytes(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str,
    ) -> StoredFileMetadata:
        path_encoded = urllib.parse.quote(path, safe="/")
        url = f"{self._base_url}/storage/v1/object/{self._bucket}/{path_encoded}"
        headers = {
            **self._headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

        async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
            response = await client.post(url, content=content)

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Erro ao enviar arquivo ao storage: HTTP {response.status_code}: {response.text[:200]}"
            )

        return StoredFileMetadata(
            path=path,
            size=len(content),
            content_type=content_type,
            exists=True,
        )

    async def delete_file(self, bucket: str, path: str) -> None:
        """
        Deleta um arquivo do Supabase Storage.
        Endpoint: DELETE /storage/v1/object/{bucket}/{path}
        """
        path_encoded = urllib.parse.quote(path, safe="/")
        url = f"{self._base_url}/storage/v1/object/{self._bucket}/{path_encoded}"

        async with httpx.AsyncClient(headers=self._headers, timeout=30.0) as client:
            response = await client.delete(url)

        if response.status_code not in (200, 204, 404):
            raise RuntimeError(
                f"Erro ao deletar arquivo: HTTP {response.status_code}: {response.text[:200]}"
            )
