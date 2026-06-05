from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from functools import lru_cache
from pydantic import Field, field_validator, model_validator

CookieSameSite = Literal["lax", "none", "strict"]


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
    refresh_cookie_domain: str | None = None
    # SameSite do cookie de refresh. Em dev usa "lax" (localhost, sem Secure).
    # Em prod padrão é "none" (cross-site), mas deve ser trocado para "lax" quando
    # frontend e backend compartilham o mesmo domínio registrável (ex: app.engify.com
    # + api.engify.com). Isso é necessário para iOS Safari (ITP bloqueia SameSite=None).
    refresh_cookie_samesite: CookieSameSite | None = None

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

    # Arky Copilot — IA via OpenRouter (camada provider-agnostica)
    arky_openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Identificacao opcional enviada ao OpenRouter (rankings/limites de uso).
    openrouter_site_url: str = ""
    openrouter_app_name: str = "Engify Arky"
    # Overrides opcionais das cadeias de fallback por papel (ids separados por
    # virgula). Vazio = usa o catalogo curado (app.infra.ai.model_catalog).
    # Permite trocar modelos sem deploy de codigo.
    openrouter_models_weak: str = ""
    openrouter_models_strong: str = ""
    openrouter_models_vision: str = ""
    arky_enabled: bool = True
    # Tempo (segundos) que um modelo com falha transitoria fica em "cooldown" e e
    # pulado nas proximas chamadas, preservando performance/custo. Reset automatico
    # ao expirar. Padrao 45 min. 0 desativa o cache.
    arky_model_cooldown_seconds: int = 2700

    @property
    def openrouter_model_overrides(self) -> dict[str, list[str]]:
        """Overrides de cadeia por papel, parseados de env. Vazio => sem override."""
        def _parse(value: str) -> list[str]:
            return [item.strip() for item in value.split(",") if item.strip()]

        overrides: dict[str, list[str]] = {}
        if self.openrouter_models_weak:
            overrides["weak"] = _parse(self.openrouter_models_weak)
        if self.openrouter_models_strong:
            overrides["strong"] = _parse(self.openrouter_models_strong)
        if self.openrouter_models_vision:
            overrides["vision"] = _parse(self.openrouter_models_vision)
        return overrides

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

        # SameSite default: "lax" em dev (localhost, sem cross-site), "none" em prod.
        # Para corrigir mobile (iOS Safari ITP), defina REFRESH_COOKIE_SAMESITE=lax
        # em produção após configurar domínio same-site (ex: api.engify.com).
        if self.refresh_cookie_samesite is None:
            self.refresh_cookie_samesite = "lax" if self.environment == "dev" else "none"

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
