from pydantic import BaseModel, field_validator
from uuid import UUID
from typing import Literal


ResourceType = Literal["obra", "item", "financeiro", "mural"]

ALLOWED_UPLOAD_TYPES = {
    "obra":       {"image/jpeg", "image/png", "image/webp"},
    "item":       {"image/jpeg", "image/png", "image/webp"},
    "financeiro": {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    "mural":      {"image/jpeg", "image/png", "image/webp", "application/pdf"},
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


class DownloadUrlRequest(BaseModel):
    path: str


class DownloadUrlResponse(BaseModel):
    download_url: str
    expires_in: int
