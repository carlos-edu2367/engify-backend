from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.entities.obra import Obra
from app.domain.entities.money import Money


def _make_obra(team_id, categoria_id, title="Obra A", valor="1000.00", total_recebido="1000.00"):
    obra = Obra(
        title=title,
        team_id=team_id,
        responsavel_id=None,
        description="",
        id=uuid4(),
        valor=Money(Decimal(valor)),
        categoria_id=categoria_id,
        total_recebido=Decimal(total_recebido),
    )
    return obra


def test_excel_builder_uses_fixed_percentage_cell_and_totals(team_id):
    from app.application.providers.utility.excel_report_builder import (
        CommissionReportRow,
        ExcelReportBuilder,
    )

    categoria_id = uuid4()
    builder = ExcelReportBuilder()
    rows = [
        CommissionReportRow(
            obra_id=uuid4(),
            titulo="Obra 1",
            valor_total=Decimal("1500.00"),
            ultimo_recebimento=datetime(2026, 5, 20, tzinfo=timezone.utc),
        ),
        CommissionReportRow(
            obra_id=uuid4(),
            titulo="Obra 2",
            valor_total=Decimal("2500.00"),
            ultimo_recebimento=datetime(2026, 5, 25, tzinfo=timezone.utc),
        ),
    ]

    content = builder.build_monthly_commission_report(
        team_id=team_id,
        categoria_id=categoria_id,
        categoria_nome="Residencial",
        mes=5,
        ano=2026,
        porcentagem_comissao=Decimal("0.05"),
        rows=rows,
    )

    workbook = builder.load_workbook(content)
    sheet = workbook["Relatorio"]

    assert sheet["B3"].value == pytest.approx(0.05)
    assert sheet["C6"].value == "=B6*$B$3"
    assert sheet["C7"].value == "=B7*$B$3"
    assert sheet["B9"].value == "=SUM(B6:B7)"
    assert sheet["C9"].value == "=SUM(C6:C7)"
    assert sheet["A6"].value == "Obra 1"
    assert sheet["A7"].value == "Obra 2"


def test_excel_builder_sanitizes_formula_like_titles(team_id):
    from app.application.providers.utility.excel_report_builder import (
        CommissionReportRow,
        ExcelReportBuilder,
    )

    builder = ExcelReportBuilder()
    rows = [
        CommissionReportRow(
            obra_id=uuid4(),
            titulo="=HYPERLINK(\"http://malicioso\")",
            valor_total=Decimal("500.00"),
            ultimo_recebimento=datetime(2026, 5, 20, tzinfo=timezone.utc),
        ),
    ]

    content = builder.build_monthly_commission_report(
        team_id=team_id,
        categoria_id=uuid4(),
        categoria_nome="Categoria",
        mes=5,
        ano=2026,
        porcentagem_comissao=Decimal("0.10"),
        rows=rows,
    )

    workbook = builder.load_workbook(content)
    sheet = workbook["Relatorio"]

    assert sheet["A6"].value == "'=HYPERLINK(\"http://malicioso\")"


@pytest.mark.asyncio
async def test_generate_monthly_commission_report_creates_pending_job(team_id):
    from app.application.use_cases.generate_monthly_commission_report import (
        GenerateMonthlyCommissionReportInput,
        GenerateMonthlyCommissionReportUseCase,
    )

    categoria_id = uuid4()
    report_job_repo = AsyncMock()
    categoria_repo = AsyncMock()
    queue = AsyncMock()
    uow = AsyncMock()

    categoria_repo.get_by_id.return_value = object()
    saved_job = AsyncMock()
    saved_job.id = uuid4()
    saved_job.status = "pending"
    report_job_repo.save.return_value = saved_job

    use_case = GenerateMonthlyCommissionReportUseCase(
        report_job_repo=report_job_repo,
        categoria_repo=categoria_repo,
        job_queue=queue,
        uow=uow,
    )

    result = await use_case.execute(
        GenerateMonthlyCommissionReportInput(
            user_id=uuid4(),
            team_id=team_id,
            categoria_id=categoria_id,
            mes=5,
            ano=2026,
            porcentagem_comissao=Decimal("0.05"),
        )
    )

    assert result.job_id == saved_job.id
    categoria_repo.get_by_id.assert_awaited_once_with(categoria_id, team_id)
    report_job_repo.save.assert_awaited_once()
    queue.enqueue_generate_commission_report.assert_awaited_once_with(saved_job.id)
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_monthly_commission_report_rejects_invalid_percentage(team_id):
    from app.application.use_cases.generate_monthly_commission_report import (
        GenerateMonthlyCommissionReportInput,
        GenerateMonthlyCommissionReportUseCase,
    )
    from app.domain.errors import DomainError

    use_case = GenerateMonthlyCommissionReportUseCase(
        report_job_repo=AsyncMock(),
        categoria_repo=AsyncMock(),
        job_queue=AsyncMock(),
        uow=AsyncMock(),
    )

    with pytest.raises(DomainError, match="comiss"):
        await use_case.execute(
            GenerateMonthlyCommissionReportInput(
                user_id=uuid4(),
                team_id=team_id,
                categoria_id=uuid4(),
                mes=5,
                ano=2026,
                porcentagem_comissao=Decimal("1.50"),
            )
        )


@pytest.mark.asyncio
async def test_get_report_job_status_is_scoped_by_tenant(team_id):
    from app.application.use_cases.generate_monthly_commission_report import (
        GetCommissionReportJobStatusInput,
        GetCommissionReportJobStatusUseCase,
    )

    job_id = uuid4()
    report_job_repo = AsyncMock()
    storage = AsyncMock()

    job = AsyncMock()
    job.status = "completed"
    job.file_path = f"reports/{team_id}/{job_id}.xlsx"
    report_job_repo.get_by_id.return_value = job
    storage.get_signed_download_url.return_value = "https://download.test/report.xlsx"

    use_case = GetCommissionReportJobStatusUseCase(
        report_job_repo=report_job_repo,
        storage_provider=storage,
    )

    result = await use_case.execute(
        GetCommissionReportJobStatusInput(team_id=team_id, job_id=job_id)
    )

    assert result.status == "completed"
    assert result.file_url == "https://download.test/report.xlsx"
    report_job_repo.get_by_id.assert_awaited_once_with(job_id, team_id)
