from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from app.domain.errors import DomainError


class ReportJobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportJob:
    def __init__(
        self,
        team_id: UUID,
        type: str,
        input_data: dict,
        requested_by_user_id: UUID | None = None,
        id: UUID | None = None,
        status: ReportJobStatus = ReportJobStatus.PENDING,
        file_path: str | None = None,
        error_message: str | None = None,
        attempts: int = 0,
        created_at: datetime | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        failed_at: datetime | None = None,
    ) -> None:
        if not type or not type.strip():
            raise DomainError("Tipo do job de relatorio e obrigatorio")
        self.id = id or uuid4()
        self.team_id = team_id
        self.requested_by_user_id = requested_by_user_id
        self.type = type.strip()
        self.status = status
        self.input_data = input_data
        self.file_path = file_path
        self.error_message = error_message
        self.attempts = attempts
        self.created_at = created_at or datetime.now(timezone.utc)
        self.started_at = started_at
        self.completed_at = completed_at
        self.failed_at = failed_at

    def mark_processing(self) -> None:
        self.status = ReportJobStatus.PROCESSING
        self.started_at = datetime.now(timezone.utc)
        self.error_message = None
        self.attempts += 1

    def mark_completed(self, file_path: str) -> None:
        self.status = ReportJobStatus.COMPLETED
        self.file_path = file_path
        self.error_message = None
        self.completed_at = datetime.now(timezone.utc)
        self.failed_at = None

    def mark_failed(self, message: str) -> None:
        self.status = ReportJobStatus.FAILED
        self.error_message = message[:1000]
        self.failed_at = datetime.now(timezone.utc)

