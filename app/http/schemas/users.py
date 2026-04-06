from pydantic import BaseModel, EmailStr
from uuid import UUID
from app.domain.entities.user import Roles


class UserResponse(BaseModel):
    id: UUID
    nome: str
    email: str
    role: Roles
    team_id: UUID


class UserListItem(BaseModel):
    user_id: UUID
    nome: str
    email: str
    role: Roles


class UpdateMeRequest(BaseModel):
    nome: str | None = None
    email: EmailStr | None = None
