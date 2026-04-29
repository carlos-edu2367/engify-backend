from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError
from app.http.dependencies.services import get_session
from app.infra.db.repositories.user_repository import UserRepositoryImpl


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    payload = getattr(request.state, "jwt_payload", None)
    if not payload:
        raise HTTPException(status_code=401, detail="Nao autenticado")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Token invalido")

    try:
        user_repo = UserRepositoryImpl(session)
        user = await user_repo.get_by_id(UUID(user_id_str))
    except DomainError:
        raise HTTPException(status_code=401, detail="Usuario nao encontrado")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != Roles.ADMIN:
        raise HTTPException(status_code=403, detail="Acao restrita a administradores")
    return user


def require_manager(user: CurrentUser) -> User:
    allowed = {Roles.ADMIN, Roles.ENGENHEIRO, Roles.FINANCEIRO}
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Acesso nao autorizado")
    return user


def require_engineer(user: CurrentUser) -> User:
    allowed = {Roles.ADMIN, Roles.ENGENHEIRO}
    if user.role not in allowed:
        raise HTTPException(
            status_code=403,
            detail="Acao restrita a administradores ou engenheiros",
        )
    return user


def require_financeiro(user: CurrentUser) -> User:
    allowed = {Roles.ADMIN, Roles.FINANCEIRO}
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Acao restrita ao modulo financeiro")
    return user


def require_rh_admin(user: CurrentUser) -> User:
    allowed = {Roles.ADMIN, Roles.FINANCEIRO}
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Acesso restrito ao RH")
    return user


def require_funcionario(user: CurrentUser) -> User:
    if user.role != Roles.FUNCIONARIO:
        raise HTTPException(status_code=403, detail="Acesso restrito a funcionarios")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
ManagerUser = Annotated[User, Depends(require_manager)]
EngineerUser = Annotated[User, Depends(require_engineer)]
FinanceiroUser = Annotated[User, Depends(require_financeiro)]
RHAdminUser = Annotated[User, Depends(require_rh_admin)]
FuncionarioUser = Annotated[User, Depends(require_funcionario)]
