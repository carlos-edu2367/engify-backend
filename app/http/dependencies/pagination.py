from typing import Annotated
from fastapi import Query, Depends
from dataclasses import dataclass


@dataclass
class PaginationParams:
    page: int
    limit: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


async def get_pagination(
    page: Annotated[int, Query(ge=1, description="Número da página")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Itens por página (máx 100)")] = 20,
) -> PaginationParams:
    return PaginationParams(page=page, limit=limit)


Pagination = Annotated[PaginationParams, Depends(get_pagination)]
