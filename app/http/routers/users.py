import json
from fastapi import APIRouter, HTTPException
from sqlalchemy import delete as sa_delete
from uuid import UUID

from app.http.schemas.users import UserResponse, UserListItem, UpdateMeRequest
from app.http.schemas.common import MessageResponse
from app.http.dependencies.auth import CurrentUser, AdminUser, EngineerUser
from app.http.dependencies.services import UserServiceDep, Session
from app.infra.db.repositories.user_repository import UserRepositoryImpl
from app.infra.db.models.user_model import UserModel
from app.infra.db.uow import SQLAlchemyUOW
from app.infra.cache.client import get_redis
from app.infra.cache.keys import users_list_key
from app.domain.errors import DomainError

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUser):
    """Perfil do usuário autenticado."""
    return UserResponse(
        id=user.id,
        nome=user.nome,
        email=user.email,
        role=user.role,
        team_id=user.team.id,
    )


@router.put("/me", response_model=UserResponse)
async def update_me(body: UpdateMeRequest, user: CurrentUser, session: Session):
    """Atualiza nome e/ou e-mail do próprio usuário."""
    if not body.nome and not body.email:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar")

    repo = UserRepositoryImpl(session)
    uow = SQLAlchemyUOW(session)

    if body.nome:
        user.nome = body.nome
    if body.email:
        user.email = body.email

    saved = await repo.save(user)
    await uow.commit()

    # Invalida cache da lista do time
    redis = get_redis()
    await redis.delete(users_list_key(user.team.id))

    return UserResponse(
        id=saved.id, nome=saved.nome,
        email=saved.email, role=saved.role, team_id=saved.team.id,
    )


@router.get("", response_model=list[UserListItem])
async def list_team_users(user: EngineerUser, session: Session):
    """
    Lista todos os usuários do time. Cache Redis 10min.
    Restrito a ADMIN e ENGENHEIRO.
    """
    redis = get_redis()
    cache_key = users_list_key(user.team.id)

    cached = await redis.get(cache_key)
    if cached:
        return [UserListItem.model_validate(u) for u in json.loads(cached)]

    repo = UserRepositoryImpl(session)
    users = await repo.get_by_team_id(user.team.id)

    result = [
        UserListItem(user_id=u.user_id, nome=u.nome, email=u.email, role=u.role)
        for u in users
    ]
    await redis.set(
        cache_key,
        json.dumps([u.model_dump(mode="json") for u in result]),
        ex=600,
    )
    return result


@router.delete("/{user_id}", response_model=MessageResponse)
async def remove_user(user_id: UUID, admin: AdminUser, session: Session):
    """
    Remove um usuário do time.
    Não é possível remover a si mesmo.
    Restrito a ADMIN.
    """
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Você não pode remover a si mesmo")

    repo = UserRepositoryImpl(session)
    try:
        target = await repo.get_by_id(user_id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if target.team.id != admin.team.id:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    stmt = sa_delete(UserModel).where(
        UserModel.id == user_id,
        UserModel.team_id == admin.team.id,
    )
    await session.execute(stmt)
    uow = SQLAlchemyUOW(session)
    await uow.commit()

    # Invalida cache da lista
    redis = get_redis()
    await redis.delete(users_list_key(admin.team.id))

    return MessageResponse(message="Usuário removido com sucesso")
