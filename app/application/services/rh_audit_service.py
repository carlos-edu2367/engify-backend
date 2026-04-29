from app.application.providers.repo.rh_repo import RhAuditLogRepository
from app.application.providers.uow import UOWProvider
from app.domain.entities.rh import RhAuditLog


class RhAuditService:
    def __init__(self, audit_repo: RhAuditLogRepository, uow: UOWProvider) -> None:
        self.audit_repo = audit_repo
        self.uow = uow

    @staticmethod
    def _mask_dict(payload: dict | None) -> dict | None:
        if payload is None:
            return None
        return RhAuditService._mask_value(payload)

    @staticmethod
    def _mask_value(value):
        if isinstance(value, dict):
            masked: dict = {}
            for key, nested_value in value.items():
                lowered = key.lower()
                if "cpf" in lowered and isinstance(nested_value, str):
                    digits = "".join(ch for ch in nested_value if ch.isdigit())
                    masked[key] = f"***{digits[-4:]}" if digits else "***"
                    continue
                if "salario" in lowered or "salary" in lowered:
                    masked[key] = "***"
                    continue
                if "file_path" in lowered or "document" in lowered or "download_url" in lowered:
                    masked[key] = "***"
                    continue
                if lowered in {"latitude", "longitude", "lat", "lng", "lon"}:
                    masked[key] = "***"
                    continue
                masked[key] = RhAuditService._mask_value(nested_value)
            return masked
        if isinstance(value, list):
            return [RhAuditService._mask_value(item) for item in value]
        return value

    async def record(self, event: RhAuditLog) -> RhAuditLog:
        event.before = self._mask_dict(event.before)
        event.after = self._mask_dict(event.after)
        saved = await self.audit_repo.save(event)
        await self.uow.commit()
        return saved
