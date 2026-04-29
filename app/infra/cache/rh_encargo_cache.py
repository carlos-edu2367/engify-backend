from uuid import UUID

from app.application.providers.utility.rh_encargo_cache import RhEncargoCachePort
from app.domain.entities.rh import RegraEncargo


class NullRhEncargoCache(RhEncargoCachePort):
    async def get_active_rules(self, team_id: UUID, ano: int, mes: int) -> list[RegraEncargo] | None:
        return None

    async def set_active_rules(self, team_id: UUID, ano: int, mes: int, regras: list[RegraEncargo]) -> None:
        return None

    async def invalidate_team(self, team_id: UUID) -> None:
        return None
