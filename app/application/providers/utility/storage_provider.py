from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class DirectUploadRequest:
    bucket: str
    path: str
    content_type: str
    expires_in: int = 600


@dataclass(frozen=True)
class DirectUploadData:
    upload_url: str
    path: str
    token: Optional[str] = None
    headers: dict[str, str] | None = None


@dataclass(frozen=True)
class StoredFileMetadata:
    path: str
    size: int
    content_type: Optional[str]
    exists: bool

class StorageProvider(ABC):
    @abstractmethod
    async def create_direct_upload(self, request: DirectUploadRequest) -> DirectUploadData:
        pass

    @abstractmethod
    async def get_file_metadata(self, bucket: str, path: str) -> StoredFileMetadata:
        pass

    @abstractmethod
    async def get_signed_download_url(
        self,
        bucket: str,
        path: str,
        expires_in: int = 3600
    ) -> str:
        pass

    @abstractmethod
    async def delete_file(
            self,
            bucket: str,
            path: str
        ) -> None:
        pass