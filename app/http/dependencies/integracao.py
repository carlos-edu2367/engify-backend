"""
Autenticação dos endpoints de integração (máquina-a-máquina).

Distinta da auth humana: valida o token de integração (`type=integration`),
carrega a `ArcaikaConnection` e **reaplica RLS** com o team_id da conexão
(a request não passou pelo TenantMiddleware humano). O team_id vem sempre da
conexão — nunca do corpo/headers do cliente.
"""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from jose import JWTError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.http.dependencies.services import get_session
from app.infra.security.integration_tokens import decode_integration_access_token
from app.infra.db.repositories.integracao_repository import ArcaikaConnectionRepositoryImpl
from app.domain.entities.integracao import ArcaikaConnection


async def get_integration_principal(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ArcaikaConnection:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de integração ausente")
    token = auth[len("Bearer "):]
    try:
        payload = decode_integration_access_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token de integração inválido")

    try:
        conn_id = UUID(payload["conn_id"])
        team_id = UUID(payload["team_id"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token de integração malformado")

    repo = ArcaikaConnectionRepositoryImpl(session)
    connection = await repo.get_by_id(conn_id)
    if connection is None or not connection.is_active or connection.team_id != team_id:
        raise HTTPException(status_code=401, detail="Conexão inválida ou revogada")

    # Reaplica RLS (defesa em profundidade) — a request não passou pelo TenantMiddleware.
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(connection.team_id)},
    )
    request.state.team_id = connection.team_id
    return connection


IntegrationPrincipal = Annotated[ArcaikaConnection, Depends(get_integration_principal)]
