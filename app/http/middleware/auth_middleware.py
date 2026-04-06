from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from jose import JWTError
from app.infra.security.jwt import decode_access_token


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Extrai e valida o JWT do header Authorization.
    Se válido, injeta o payload em request.state.jwt_payload.
    Rotas públicas simplesmente não terão jwt_payload no state —
    o controle de acesso é feito pelas dependencies do FastAPI.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]
            try:
                payload = decode_access_token(token)
                request.state.jwt_payload = payload
            except JWTError:
                # Token inválido/expirado — não injeta nada.
                # As dependencies de rotas protegidas irão levantar 401.
                pass

        return await call_next(request)
