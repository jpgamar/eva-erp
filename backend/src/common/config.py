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
    eva_billing_bridge_secret: str = ""
    eva_billing_bridge_skew_seconds: int = 300
    eva_api_base_url: str = "https://api.goeva.ai"
    eva_admin_api_key: str = "874c7c7b567e6ce1c260c65688b9a75a6641b6dcab2ebe15f7cfb0da7080317d"
    eva_api_timeout_seconds: float = 20.0

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Stripe
    eva_stripe_secret_key: str = ""
    eva_stripe_webhook_secret: str = ""
    stripe_webhook_secret_erp: str = ""
    stripe_tax_enabled: bool = True
    stripe_reconciliation_enabled: bool = True
    stripe_reconciliation_interval_seconds: int = 86400
    finance_kpi_source: str = "lifecycle"

    # Canonical Stripe Products — STANDARD/PRO × persona moral/fisica.
    # First-time Checkout reuses these instead of creating one-off Products.
    # Populated by running Eva's bootstrap script once per environment.
    stripe_product_standard_moral_mxn: str = ""
    stripe_product_standard_fisica_mxn: str = ""
    stripe_product_pro_moral_mxn: str = ""
    stripe_product_pro_fisica_mxn: str = ""

    # Feature flag — gates new Kanban UI + /subscription/apply proxy endpoints
    # + APScheduler fiscal sync retry worker. Schema migrations always run.
    feature_erp_empresas_pipeline: bool = False

    # Feature flag — when an operator edits an empresa's ZIP and the resulting
    # cedular rule would change the payable (customer moved into/out of GTO,
    # for example), auto-reprice the Stripe subscription (new Price + item
    # swap, proration_behavior=none). Off by default while we validate in
    # staging. The quote math always updates regardless of this flag.
    enable_cedular_auto_reprice: bool = False

    # Supabase Storage bucket for constancia PDFs (Phase 4 F4.9).
    supabase_bucket_constancias: str = "empresa-constancias"

    # EVA DB (read-only)
    eva_database_url: str = ""

    # Supabase Admin (Eva platform provisioning)
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # OpenAI
    openai_api_key: str = ""
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "no-reply@goeva.ai"
    sendgrid_from_name: str = "EvaAI"
    sendgrid_reply_to: str = "hi@goeva.ai"
    sendgrid_logo_url: str = "https://app.goeva.ai/favicon.ico"
    billing_invoice_from_email: str = "hi@goeva.ai"
    billing_invoice_from_name: str = "EvaAI"
    eva_app_onboarding_redirect_url: str = "https://app.goeva.ai/auth/change-password"

    # Facturapi (CFDI electronic invoicing)
    facturapi_api_key: str = ""

    # Outbox pattern: async worker that timbres pending facturas with retries.
    # Fixes the F-4-class bug where a FacturAPI stamp success followed by a
    # DB commit failure left a valid CFDI in SAT with no ERP row.
    facturapi_outbox_enabled: bool = True
    facturapi_outbox_interval_seconds: int = 30
    facturapi_outbox_max_retries: int = 5

    # Reconciliation: periodic FacturAPI → ERP sync that adopts any CFDI
    # emitted outside the ERP (manual dashboard stamps, legacy records)
    # and recovers from outbox retries that exhausted their attempts.
    facturapi_reconciliation_enabled: bool = True
    facturapi_reconciliation_interval_seconds: int = 3600

    # SSO handoff from EvaAI (shared secret with EvaAI backend)
    erp_sso_secret: str = ""

    # OpenClaw Infrastructure (SSH access to runtime hosts)
    eva_ssh_private_key_base64: str = ""
    hetzner_api_token: str = ""

    # Frontend
    frontend_url: str = "https://erp.goeva.ai"
    eva_app_base_url: str = "https://app.goeva.ai"

    # Environment
    environment: str = "development"
    vault_session_ttl_minutes: int = 0

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
    monitoring_supabase_auth_api_key: str = ""
    monitoring_fmac_erp_frontend_url: str = "https://erp.fmaccesorios.com"
    monitoring_fmac_erp_backend_url: str = "https://erp.fmaccesorios.com/api/v1/products"
    monitoring_fmac_erp_db_url: str = ""
    monitoring_sendgrid_fmac_url: str = "https://erp.fmaccesorios.com/api/v1/health/sendgrid"
    monitoring_sendgrid_fmac_api_key: str = ""
    monitoring_facturapi_fmac_url: str = "https://www.facturapi.io/v2/invoices?limit=1"
    monitoring_facturapi_eva_erp_url: str = "https://www.facturapi.io/v2/invoices?limit=1"
    monitoring_facturapi_eva_app_url: str = "https://www.facturapi.io/v2/invoices?limit=1"
    monitoring_facturapi_fmac_api_key: str = ""
    monitoring_facturapi_eva_erp_api_key: str = ""
    monitoring_facturapi_eva_app_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
