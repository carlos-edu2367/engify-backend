"""ArkyAuditService — dedicated audit trail for all Arky interactions."""
import logging

from app.application.providers.repo.arky_repo import ArkyAuditLogRepository
from app.application.providers.uow import UOWProvider
from app.domain.entities.arky import ArkyAuditLog

logger = logging.getLogger(__name__)

# Fields to redact from tool params before logging
_REDACT_KEYS = frozenset({
    "cpf", "pix", "chave_pix", "senha", "password", "token",
    "secret", "api_key", "jwt", "salario", "salary",
    "download_url", "signed_url", "file_path", "latitude",
    "longitude", "lat", "lng",
})


def _redact(value):
    if isinstance(value, dict):
        return {
            k: "***" if k.lower() in _REDACT_KEYS else _redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class ArkyAuditService:
    def __init__(
        self, audit_repo: ArkyAuditLogRepository, uow: UOWProvider
    ) -> None:
        self._repo = audit_repo
        self._uow = uow

    async def record(self, log: ArkyAuditLog) -> None:
        log.tool_params_masked = _redact(log.tool_params_masked)
        try:
            await self._repo.save(log)
            await self._uow.commit()
        except Exception as e:
            logger.error("Failed to save Arky audit log: %s", e)
            # Audit failure must never break the user flow
