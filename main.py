from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.limiter import limiter
from app.http.middleware.auth_middleware import AuthMiddleware
from app.http.middleware.tenant_middleware import TenantMiddleware
from app.http.middleware.security_headers import SecurityHeadersMiddleware
from app.http.middleware.error_middleware import register_exception_handlers
from app.http.routers import auth
from app.http.routers import teams, users, obras, items, diarias, financeiro, storage
from app.http.routers import mural
from app.http.routers import public_obras
from app.http.routers import categorias_obras
from app.http.routers import notificacoes
from app.http.routers import rh

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.environment != "prod" else None,
    redoc_url="/redoc" if settings.environment != "prod" else None,
    openapi_url="/openapi.json" if settings.environment != "prod" else None,
    lifespan=lifespan,
)

# ── Rate limiter ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Middlewares ───────────────────────────────────────────────────────────────
# No Starlette, o ÚLTIMO add_middleware é o mais externo (primeiro a receber requests).
# Ordem de execução na request: CORS → Auth → Tenant → Security → Route
#
# CORS precisa ser o mais externo para garantir headers CORS em TODOS os responses,
# incluindo 401/403 retornados pelo TenantMiddleware.

# 4. Innermost: SecurityHeaders (decoram o response antes de sair)
app.add_middleware(SecurityHeadersMiddleware)

# 3. Inner: TenantMiddleware (depende do jwt_payload injetado pelo Auth)
app.add_middleware(TenantMiddleware)

# 2. Middle: AuthMiddleware (extrai JWT antes do Tenant)
app.add_middleware(AuthMiddleware)

# 1. Outermost: CORS (adicionado por último = executado primeiro na request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ────────────────────────────────────────────────────────
register_exception_handlers(app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(teams.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(obras.router, prefix=settings.api_prefix)
app.include_router(items.router, prefix=settings.api_prefix)
app.include_router(diarias.router, prefix=settings.api_prefix)
app.include_router(financeiro.router, prefix=settings.api_prefix)
app.include_router(storage.router, prefix=settings.api_prefix)
app.include_router(mural.router, prefix=settings.api_prefix)
app.include_router(public_obras.router, prefix=settings.api_prefix)
app.include_router(categorias_obras.router, prefix=settings.api_prefix)
app.include_router(notificacoes.router, prefix=settings.api_prefix)
app.include_router(rh.router, prefix=settings.api_prefix)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], include_in_schema=False)
async def health():
    return {"status": "ok", "env": settings.environment}
