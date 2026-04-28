from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateCommissionReportRequest(BaseModel):
    categoria_id: UUID
    mes: int = Field(ge=1, le=12)
    ano: int = Field(ge=2000, le=2100)
    porcentagem_comissao: Decimal


class CreateCommissionReportResponse(BaseModel):
    job_id: UUID


class CommissionReportJobStatusResponse(BaseModel):
    status: str
    file_url: str | None = None
    error_message: str | None = None
