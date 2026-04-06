from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    has_next: bool

    @classmethod
    def build(cls, items: list[T], page: int, limit: int, total: int) -> "PaginatedResponse[T]":
        return cls(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_next=(page * limit) < total,
        )


class MessageResponse(BaseModel):
    message: str
