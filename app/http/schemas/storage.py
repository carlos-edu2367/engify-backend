from pydantic import BaseModel, field_validator
from uuid import UUID
from typing import Literal

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
_DOC_TYPES   = {"application/pdf"}

ResourceType = Literal["obra", "item", "financeiro", "mural"]

ALLOWED_UPLOAD_TYPES = {
    "obra":       _IMAGE_TYPES | _VIDEO_TYPES,
    "item":       _IMAGE_TYPES,
    "financeiro": _IMAGE_TYPES | _DOC_TYPES,
    "mural":      _IMAGE_TYPES | _DOC_TYPES,
}


class UploadUrlRequest(BaseModel):
    resource_type: ResourceType
    resource_id: UUID
    file_name: str
    content_type: str

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str, info) -> str:
        # Validation is context-dependent (resource_type); done in the router
        return v


class UploadUrlResponse(BaseModel):
    upload_url: str
    path: str
    expires_in: int


class BatchUploadUrlItem(BaseModel):
    file_name: str
    content_type: str


class BatchUploadUrlRequest(BaseModel):
    resource_type: ResourceType
    resource_id: UUID
    files: list[BatchUploadUrlItem]


class BatchUploadUrlResponse(BaseModel):
    uploads: list[UploadUrlResponse]


class DownloadUrlRequest(BaseModel):
    path: str


class DownloadUrlResponse(BaseModel):
    download_url: str
    expires_in: int
