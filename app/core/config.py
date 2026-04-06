from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Engify API"
    environment: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database (PostgreSQL + asyncpg)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/engify"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True
    db_pool_recycle: int = 3600

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_default_ttl: int = 60  # segundos

    # JWT — JWT_SECRET deve estar definida no ambiente; sem default para forçar configuração explícita
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Email (Mailgun) — opcional; se não configurado, emails são suprimidos com log de aviso
    mailgun_api_key: str = ""
    mailgun_domain: str = ""
    mailgun_from: str = "noreply@engify.app"
    frontend_url: str = "https://engify-frontend.vercel.app" if environment == "prod" else "http://localhost:5174"

    # Storage — Supabase Storage REST API
    # storage_url: https://<project-ref>.supabase.co
    # storage_key: service_role key do projeto Supabase
    # storage_bucket_name: "engify" (único bucket, prefixos: obra/, item/, financeiro/)
    storage_url: str = ""
    storage_key: str = ""
    storage_bucket_name: str = "engify"
    storage_region: str = "auto"
    storage_upload_expires_in: int = 600    # 10 minutos
    storage_download_expires_in: int = 3600  # 1 hora

    # CORS
    allowed_origins: list[str] = ["https://engify-frontend.vercel.app" if environment == "prod" else "http://localhost:5174"]

    # Trial period
    trial_days: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
