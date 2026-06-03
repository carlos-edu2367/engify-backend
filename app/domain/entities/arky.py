from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

PREVIEW_EXPIRE_MINUTES = 15


@dataclass
class ArkyConversation:
    team_id: UUID
    user_id: UUID
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ArkyMessage:
    conversation_id: UUID
    team_id: UUID
    user_id: UUID
    role: str  # "user" | "assistant"
    content: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ArkyAuditLog:
    team_id: UUID
    user_id: UUID
    user_role: str
    conversation_id: UUID
    message_id: UUID
    route: str
    status: str  # "ok" | "error" | "policy_denied" | "tool_error"
    id: UUID = field(default_factory=uuid4)
    module: str | None = None
    intent: str | None = None
    model_used: str | None = None
    model_family: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int | None = None
    tools_called: list[str] = field(default_factory=list)
    tool_params_masked: dict | None = None
    rag_chunk_ids: list[str] = field(default_factory=list)
    action_preview_id: UUID | None = None
    error_code: str | None = None
    request_id: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ArkyActionPreview:
    team_id: UUID
    user_id: UUID
    conversation_id: UUID
    action_type: str
    payload: dict
    summary: str
    risk_level: str
    id: UUID = field(default_factory=uuid4)
    status: str = "pending"  # "pending" | "confirmed" | "rejected" | "expired"
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
        + timedelta(minutes=PREVIEW_EXPIRE_MINUTES)
    )
    confirmed_at: datetime | None = None
    rejected_at: datetime | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def confirm(self) -> None:
        if self.status != "pending":
            raise ValueError(f"Ação não pode ser confirmada no status '{self.status}'")
        if self.is_expired():
            self.status = "expired"
            raise ValueError("A prévia da ação expirou")
        self.status = "confirmed"
        self.confirmed_at = datetime.now(timezone.utc)

    def reject(self) -> None:
        if self.status != "pending":
            raise ValueError(f"Ação não pode ser rejeitada no status '{self.status}'")
        self.status = "rejected"
        self.rejected_at = datetime.now(timezone.utc)
