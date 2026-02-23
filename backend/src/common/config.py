from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:54322/eva_erp"

    # JWT
    jwt_secret_key: str = "change-me-to-a-random-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    agent_api_key: str = ""
    agent_api_actor_email: str = ""

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

    # Monitoring
    monitoring_enabled: bool = True
    monitoring_interval_seconds: int = 30
    monitoring_check_timeout_seconds: float = 8.0
    monitoring_failure_threshold_critical: int = 2
    monitoring_failure_threshold_default: int = 3
    monitoring_recovery_threshold: int = 2
    monitoring_stale_after_seconds: int = 120
    monitoring_slack_webhook_url: str = ""

    # Monitoring target URLs
    monitoring_frontend_url: str = "https://app.goeva.ai"  # legacy fallback
    monitoring_erp_frontend_url: str = "https://erp.goeva.ai"
    monitoring_eva_app_frontend_url: str = "https://app.goeva.ai"
    monitoring_erp_api_health_url: str = "https://eva-erp-goevaai-30a99658.koyeb.app/health/readiness"
    monitoring_eva_api_health_url: str = "https://api.goeva.ai/api/v1/health"
    monitoring_whatsapp_health_url: str = "https://api.goeva.ai/api/v1/whatsapp/admin/webhook-health"
    monitoring_supabase_url: str = ""
    monitoring_fmac_erp_frontend_url: str = "https://erp.fmaccesorios.com"
    monitoring_fmac_erp_backend_url: str = "https://erp.fmaccesorios.com/api/v1/products"
    monitoring_fmac_erp_db_url: str = ""
    monitoring_facturapi_fmac_url: str = "https://www.facturapi.io/v2/invoices?limit=1"
    monitoring_facturapi_eva_erp_url: str = "https://www.facturapi.io/v2/invoices?limit=1"
    monitoring_facturapi_eva_app_url: str = "https://www.facturapi.io/v2/invoices?limit=1"
    monitoring_facturapi_fmac_api_key: str = ""
    monitoring_facturapi_eva_erp_api_key: str = ""
    monitoring_facturapi_eva_app_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
