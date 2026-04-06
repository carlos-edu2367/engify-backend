from typing import Annotated
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User, Roles
from app.domain.errors import DomainError
from app.http.dependencies.services import get_session
from app.infra.db.repositories.user_repository import UserRepositoryImpl


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """
    Extrai o usuário autenticado do request.state (injetado pelo AuthMiddleware).
    Levanta 401 se não houver token válido.
    O team_id do token é validado pelo TenantMiddleware antes desta dependency.
    """
    payload = getattr(request.state, "jwt_payload", None)
    if not payload:
        raise HTTPException(status_code=401, detail="Não autenticado")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Token inválido")

    try:
        user_repo = UserRepositoryImpl(session)
        user = await user_repo.get_by_id(UUID(user_id_str))
    except DomainError:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    """Restringe a rota a usuários com role ADMIN."""
    if user.role != Roles.ADMIN:
        raise HTTPException(status_code=403, detail="Ação restrita a administradores")
    return user


def require_manager(user: CurrentUser) -> User:
    """Restringe a rota a ADMIN, ENGENHEIRO ou FINANCEIRO (exclui CLIENTE)."""
    allowed = {Roles.ADMIN, Roles.ENGENHEIRO, Roles.FINANCEIRO}
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    return user


def require_engineer(user: CurrentUser) -> User:
    """Restringe a rota a ADMIN ou ENGENHEIRO."""
    allowed = {Roles.ADMIN, Roles.ENGENHEIRO}
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Ação restrita a administradores ou engenheiros")
    return user


def require_financeiro(user: CurrentUser) -> User:
    """Restringe a rota a ADMIN ou FINANCEIRO."""
    allowed = {Roles.ADMIN, Roles.FINANCEIRO}
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Ação restrita ao módulo financeiro")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
ManagerUser = Annotated[User, Depends(require_manager)]
EngineerUser = Annotated[User, Depends(require_engineer)]
FinanceiroUser = Annotated[User, Depends(require_financeiro)]
