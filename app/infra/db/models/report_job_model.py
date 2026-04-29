import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.report_job import ReportJob, ReportJobStatus
from app.infra.db.models.base import Base, TimestampMixin


class ReportJobModel(Base, TimestampMixin):
    __tablename__ = "report_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_report_jobs_team_status_created", "team_id", "status", "created_at"),
        Index("idx_report_jobs_team_type_created", "team_id", "type", "created_at"),
    )

    def to_domain(self) -> ReportJob:
        return ReportJob(
            id=self.id,
            team_id=self.team_id,
            requested_by_user_id=self.requested_by_user_id,
            type=self.type,
            status=ReportJobStatus(self.status),
            input_data=self.input_data or {},
            file_path=self.file_path,
            error_message=self.error_message,
            attempts=self.attempts,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            failed_at=self.failed_at,
        )

    @classmethod
    def from_domain(cls, job: ReportJob) -> "ReportJobModel":
        return cls(
            id=job.id or uuid.uuid4(),
            team_id=job.team_id,
            requested_by_user_id=job.requested_by_user_id,
            type=job.type,
            status=job.status.value,
            input_data=job.input_data,
            file_path=job.file_path,
            error_message=job.error_message,
            attempts=job.attempts,
            started_at=job.started_at,
            completed_at=job.completed_at,
            failed_at=job.failed_at,
        )

    def update_from_domain(self, job: ReportJob) -> None:
        self.status = job.status.value
        self.input_data = job.input_data
        self.file_path = job.file_path
        self.error_message = job.error_message
        self.attempts = job.attempts
        self.started_at = job.started_at
        self.completed_at = job.completed_at
        self.failed_at = job.failed_at
