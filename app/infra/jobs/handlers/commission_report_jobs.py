from uuid import UUID

from app.application.providers.utility.excel_report_builder import ExcelReportBuilder
from app.application.services.commission_report_service import CommissionReportService
from app.infra.db.repositories.obra_repository import (
    CategoriaObraRepositoryImpl,
    ObraRepositoryImpl,
)
from app.infra.db.repositories.report_job_repository import ReportJobRepositoryImpl
from app.infra.db.session import async_session_factory
from app.infra.db.uow import SQLAlchemyUOW
from app.infra.storage.s3_provider import S3StorageProvider


async def generate_commission_report_job(ctx, job_id: str) -> str:
    async with async_session_factory() as session:
        service = CommissionReportService(
            report_job_repo=ReportJobRepositoryImpl(session),
            categoria_repo=CategoriaObraRepositoryImpl(session),
            obra_repo=ObraRepositoryImpl(session),
            excel_builder=ExcelReportBuilder(),
            storage_provider=S3StorageProvider(),
            uow=SQLAlchemyUOW(session),
        )
        return await service.process_job(UUID(job_id))
