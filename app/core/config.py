from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from functools import lru_cache
from pydantic import Field, field_validator, model_validator


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
    frontend_url: str = ""

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
    allowed_origins: list[str] = Field(default_factory=list)

    # Trial period
    trial_days: int = 7

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off", "release"}:
                return False
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value):
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+asyncpg://", 1)
            if value.startswith("postgresql://"):
                return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def apply_environment_defaults(self):
        default_frontend_url = (
            "https://engify-frontend.vercel.app"
            if self.environment == "prod"
            else "http://localhost:5174"
        )

        if not self.frontend_url:
            self.frontend_url = default_frontend_url
        if not self.allowed_origins:
            self.allowed_origins = [default_frontend_url]

        return self

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
