from sqlalchemy.ext.asyncio import AsyncSession
from app.application.providers.uow import UOWProvider


class SQLAlchemyUOW(UOWProvider):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
