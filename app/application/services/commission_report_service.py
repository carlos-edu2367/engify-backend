from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import structlog

from app.application.providers.repo.obra_repo import CategoriaObraRepository, ObraRepository
from app.application.providers.repo.report_job_repo import ReportJobRepository
from app.application.providers.uow import UOWProvider
from app.application.providers.utility.excel_report_builder import ExcelReportBuilder
from app.application.providers.utility.storage_provider import StorageProvider
from app.core.config import settings
from app.domain.entities.report_job import ReportJobStatus
from app.domain.errors import DomainError

logger = structlog.get_logger()


class CommissionReportService:
    def __init__(
        self,
        report_job_repo: ReportJobRepository,
        categoria_repo: CategoriaObraRepository,
        obra_repo: ObraRepository,
        excel_builder: ExcelReportBuilder,
        storage_provider: StorageProvider,
        uow: UOWProvider,
    ) -> None:
        self.report_job_repo = report_job_repo
        self.categoria_repo = categoria_repo
        self.obra_repo = obra_repo
        self.excel_builder = excel_builder
        self.storage_provider = storage_provider
        self.uow = uow

    async def process_job(self, job_id: UUID) -> str:
        job = await self.report_job_repo.get_by_id_unscoped(job_id)
        if job.status == ReportJobStatus.COMPLETED and job.file_path:
            return job.file_path
        if job.type != "monthly_commission_report":
            raise DomainError("Tipo de job de relatorio nao suportado")

        payload = job.input_data
        categoria_id = UUID(payload["categoria_id"])
        mes = int(payload["mes"])
        ano = int(payload["ano"])
        porcentagem_comissao = Decimal(str(payload["porcentagem_comissao"]))

        categoria = await self.categoria_repo.get_by_id(categoria_id, job.team_id)
        period_start, period_end = _period_bounds(ano, mes)

        job.mark_processing()
        await self.report_job_repo.save(job)
        await self.uow.commit()

        logger.info(
            "commission_report.processing_started",
            job_id=str(job.id),
            team_id=str(job.team_id),
            categoria_id=str(categoria_id),
            mes=mes,
            ano=ano,
        )

        try:
            rows = await self.obra_repo.list_monthly_commission_eligible(
                team_id=job.team_id,
                categoria_id=categoria_id,
                period_start=period_start,
                period_end=period_end,
            )
            logger.info(
                "commission_report.eligible_obras_found",
                job_id=str(job.id),
                quantidade=len(rows),
            )

            content = self.excel_builder.build_monthly_commission_report(
                team_id=job.team_id,
                categoria_id=categoria_id,
                categoria_nome=categoria.title,
                mes=mes,
                ano=ano,
                porcentagem_comissao=porcentagem_comissao,
                rows=rows,
            )

            path = _build_report_path(job.team_id, job.id, ano, mes)
            await self.storage_provider.upload_bytes(
                bucket=settings.storage_bucket_name,
                path=path,
                content=content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            job.mark_completed(path)
            await self.report_job_repo.save(job)
            await self.uow.commit()
            logger.info(
                "commission_report.completed",
                job_id=str(job.id),
                file_path=path,
            )
            return path
        except Exception as exc:
            logger.exception("commission_report.failed", job_id=str(job.id))
            job.mark_failed(str(exc))
            await self.report_job_repo.save(job)
            await self.uow.commit()
            raise


def _period_bounds(ano: int, mes: int) -> tuple[datetime, datetime]:
    start = datetime(ano, mes, 1, tzinfo=timezone.utc)
    if mes == 12:
        end = datetime(ano + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(ano, mes + 1, 1, tzinfo=timezone.utc)
    return start, end


def _build_report_path(team_id: UUID, job_id: UUID, ano: int, mes: int) -> str:
    return f"reports/{team_id}/commission/{ano}-{mes:02d}/{job_id}.xlsx"
