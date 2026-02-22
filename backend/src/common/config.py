from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:54322/eva_erp"

    # JWT
    jwt_secret_key: str = "change-me-to-a-random-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Stripe
    eva_stripe_secret_key: str = ""

    # EVA DB (read-only)
    eva_database_url: str = ""

    # Supabase Admin (Eva platform provisioning)
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Facturapi (CFDI electronic invoicing)
    facturapi_api_key: str = ""

    # SSO handoff from EvaAI (shared secret with EvaAI backend)
    erp_sso_secret: str = ""

    # Environment
    environment: str = "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
