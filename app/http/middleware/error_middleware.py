from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.domain.errors import DomainError, InvalidArgument, WeakArgument, ExpiredPlan
import structlog

logger = structlog.get_logger()


def register_exception_handlers(app: FastAPI) -> None:
    """Registra todos os handlers de exceção na aplicação FastAPI."""

    @app.exception_handler(WeakArgument)
    async def weak_argument_handler(request: Request, exc: WeakArgument) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.detail})

    @app.exception_handler(InvalidArgument)
    async def invalid_argument_handler(request: Request, exc: InvalidArgument) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.detail})

    @app.exception_handler(ExpiredPlan)
    async def expired_plan_handler(request: Request, exc: ExpiredPlan) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"detail": "O plano do seu time expirou. Renove para continuar."},
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno. Tente novamente em instantes."},
        )
