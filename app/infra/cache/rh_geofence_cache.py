import json
from uuid import UUID

from app.application.providers.utility.rh_geofence_cache import RhGeofenceCache
from app.domain.entities.rh import LocalPonto
from app.infra.cache.client import get_redis
from app.infra.cache.keys import rh_geofences_key


class RedisRhGeofenceCache(RhGeofenceCache):
    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl_seconds = ttl_seconds

    async def get_locais(self, team_id: UUID, funcionario_id: UUID) -> list[LocalPonto] | None:
        cached = await get_redis().get(rh_geofences_key(team_id, funcionario_id))
        if not cached:
            return None
        data = json.loads(cached)
        return [
            LocalPonto(
                id=UUID(item["id"]),
                team_id=team_id,
                funcionario_id=funcionario_id,
                nome=item["nome"],
                latitude=item["latitude"],
                longitude=item["longitude"],
                raio_metros=item["raio_metros"],
            )
            for item in data
        ]

    async def set_locais(self, team_id: UUID, funcionario_id: UUID, locais: list[LocalPonto]) -> None:
        payload = json.dumps(
            [
                {
                    "id": str(local.id),
                    "nome": local.nome,
                    "latitude": local.latitude,
                    "longitude": local.longitude,
                    "raio_metros": local.raio_metros,
                }
                for local in locais
                if not local.is_deleted
            ]
        )
        await get_redis().set(rh_geofences_key(team_id, funcionario_id), payload, ex=self._ttl_seconds)

    async def invalidate(self, team_id: UUID, funcionario_id: UUID) -> None:
        await get_redis().delete(rh_geofences_key(team_id, funcionario_id))
