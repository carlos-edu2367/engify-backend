from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.application.providers.repo.obra_repo import CategoriaObraRepository
from app.application.providers.repo.report_job_repo import ReportJobRepository
from app.application.providers.uow import UOWProvider
from app.application.providers.utility.report_queue import CommissionReportQueue
from app.application.providers.utility.storage_provider import StorageProvider
from app.domain.entities.report_job import ReportJob, ReportJobStatus
from app.domain.errors import DomainError


REPORT_TYPE_MONTHLY_COMMISSION = "monthly_commission_report"


@dataclass(frozen=True)
class GenerateMonthlyCommissionReportInput:
    user_id: UUID
    team_id: UUID
    categoria_id: UUID
    mes: int
    ano: int
    porcentagem_comissao: Decimal


@dataclass(frozen=True)
class GenerateMonthlyCommissionReportOutput:
    job_id: UUID


@dataclass(frozen=True)
class GetCommissionReportJobStatusInput:
    team_id: UUID
    job_id: UUID


@dataclass(frozen=True)
class GetCommissionReportJobStatusOutput:
    status: str
    file_url: str | None = None
    error_message: str | None = None


class GenerateMonthlyCommissionReportUseCase:
    def __init__(
        self,
        report_job_repo: ReportJobRepository,
        categoria_repo: CategoriaObraRepository,
        job_queue: CommissionReportQueue,
        uow: UOWProvider,
    ) -> None:
        self.report_job_repo = report_job_repo
        self.categoria_repo = categoria_repo
        self.job_queue = job_queue
        self.uow = uow

    async def execute(
        self, input_data: GenerateMonthlyCommissionReportInput
    ) -> GenerateMonthlyCommissionReportOutput:
        _validate_input(input_data.mes, input_data.ano, input_data.porcentagem_comissao)
        await self.categoria_repo.get_by_id(input_data.categoria_id, input_data.team_id)

        job = ReportJob(
            team_id=input_data.team_id,
            requested_by_user_id=input_data.user_id,
            type=REPORT_TYPE_MONTHLY_COMMISSION,
            input_data={
                "categoria_id": str(input_data.categoria_id),
                "mes": input_data.mes,
                "ano": input_data.ano,
                "porcentagem_comissao": str(input_data.porcentagem_comissao),
            },
            status=ReportJobStatus.PENDING,
        )
        saved = await self.report_job_repo.save(job)
        await self.job_queue.enqueue_generate_commission_report(saved.id)
        await self.uow.commit()
        return GenerateMonthlyCommissionReportOutput(job_id=saved.id)


class GetCommissionReportJobStatusUseCase:
    def __init__(
        self,
        report_job_repo: ReportJobRepository,
        storage_provider: StorageProvider,
        bucket_name: str = "engify",
        download_expires_in: int = 3600,
    ) -> None:
        self.report_job_repo = report_job_repo
        self.storage_provider = storage_provider
        self.bucket_name = bucket_name
        self.download_expires_in = download_expires_in

    async def execute(
        self, input_data: GetCommissionReportJobStatusInput
    ) -> GetCommissionReportJobStatusOutput:
        job = await self.report_job_repo.get_by_id(input_data.job_id, input_data.team_id)
        file_url = None
        status = job.status.value if isinstance(job.status, ReportJobStatus) else str(job.status)
        if status == ReportJobStatus.COMPLETED.value and job.file_path:
            file_url = await self.storage_provider.get_signed_download_url(
                bucket=self.bucket_name,
                path=job.file_path,
                expires_in=self.download_expires_in,
            )
        return GetCommissionReportJobStatusOutput(
            status=status,
            file_url=file_url,
            error_message=job.error_message,
        )


def _validate_input(mes: int, ano: int, porcentagem_comissao: Decimal) -> None:
    if mes < 1 or mes > 12:
        raise DomainError("Mes do relatorio invalido")
    if ano < 2000 or ano > 2100:
        raise DomainError("Ano do relatorio invalido")
    if porcentagem_comissao < Decimal("0") or porcentagem_comissao > Decimal("1"):
        raise DomainError("Porcentagem de comissao invalida")
