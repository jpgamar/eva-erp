import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.common.config import settings
from src.common.database import engine, eva_engine
from src.empresas.reminders import empresa_item_reminder_runner_loop
from src.eva_platform.monitoring_service import monitoring_runner_loop
from src.facturas.outbox import facturas_outbox_runner_loop
from src.facturas.reconciliation import facturapi_reconciliation_runner_loop
from src.finances.stripe_service import stripe_reconciliation_runner_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background loops. Each owns a stop_event + task. On shutdown we set
    # the events, then cancel to unblock any in-flight awaits.
    loops: list[tuple[asyncio.Event, asyncio.Task]] = []

    if settings.monitoring_enabled:
        stop = asyncio.Event()
        loops.append((stop, asyncio.create_task(monitoring_runner_loop(stop))))
    if settings.stripe_reconciliation_enabled:
        stop = asyncio.Event()
        loops.append((stop, asyncio.create_task(stripe_reconciliation_runner_loop(stop))))
    # Outbox worker: timbres pending facturas with FacturAPI. Required for
    # CFDI data integrity — see src/facturas/outbox.py and the 2026-04-18
    # F-4 incident report.
    if settings.facturapi_outbox_enabled:
        stop = asyncio.Event()
        loops.append((stop, asyncio.create_task(facturas_outbox_runner_loop(stop))))
    # FacturAPI reconciliation: adopts CFDIs emitted outside the ERP
    # (dashboard, legacy scripts) and heals rows whose outbox retries
    # exhausted. Runs hourly by default.
    if settings.facturapi_reconciliation_enabled:
        stop = asyncio.Event()
        loops.append((stop, asyncio.create_task(facturapi_reconciliation_runner_loop(stop))))
    # Empresa item reminders: 24h + 1h before start_at, sent to
    # `settings.empresa_item_reminder_email` (default gus@goeva.ai).
    if settings.empresa_item_reminders_enabled:
        stop = asyncio.Event()
        loops.append((stop, asyncio.create_task(empresa_item_reminder_runner_loop(stop))))

    yield

    for stop, _ in loops:
        stop.set()
    for _, task in loops:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="EVA ERP",
    description="Internal ERP for EVA (goeva.ai)",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Router — all endpoints under /api/v1
from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

# Import and include module routers
from src.auth.router import router as auth_router
from src.users.router import router as users_router
from src.notifications.router import router as notifications_router
from src.finances.router import router as finances_router
from src.kpis.router import router as kpis_router
# Prospects router unmounted in the Empresas Pipeline unification. The import
# is kept for 1 release so rollback by reverting main.py only is safe; a
# follow-up PR drops the module entirely.
from src.prospects.router import router as prospects_router  # noqa: F401  # TODO: drop in follow-up PR
# vault/meetings/documents/okrs/assistant routers unmounted in the company
# CRM consolidation (Empresas is the single CRM/account hub). Tables remain
# until a separate data-drop plan is approved; historical meetings/interactions
# are surfaced through `/empresas/calendar` instead.
from src.facturas.router import router as facturas_router
from src.dashboard.router import router as dashboard_router
from src.eva_platform.router import router as eva_platform_router
from src.customers.router import router as customers_router
from src.agent.router import router as agent_router
from src.eva_billing.router import router as eva_billing_router
from src.empresas.router import router as empresas_router
from src.declaracion.router import router as declaracion_router
from src.facturas_recibidas.router import router as gastos_router

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(notifications_router)
# tasks/boards routers unmounted in the empresas-ux-pass consolidation.
# All tasks live in `empresa_items` now (with empresa_id NULL for internal
# tasks). The Tareas tab in /empresas is the new operator surface.
api_router.include_router(finances_router)
api_router.include_router(kpis_router)
# Prospects router unmounted — /prospects/* now returns 404. Clients should
# call /empresas with lifecycle_stage filter instead.
# api_router.include_router(prospects_router)
# Removed product surfaces (vault/meetings/documents/okrs/assistant) — see
# the company CRM consolidation plan; routes return 404 by design and are
# verified by `tests/test_removed_modules.py`.
api_router.include_router(facturas_router)
api_router.include_router(dashboard_router)
api_router.include_router(eva_platform_router)
# `customers_router` is preserved for the Facturas-side helpers
# (`frontend/src/lib/api/customers.ts` still calls it). The standalone
# Eva Customers page is gone — the workflows live under /empresas now.
api_router.include_router(customers_router)
api_router.include_router(agent_router)
api_router.include_router(eva_billing_router)
api_router.include_router(empresas_router)
api_router.include_router(gastos_router)
api_router.include_router(declaracion_router)

# Public payment link endpoints (under /api/v1 so erp.goeva.ai/api/v1/public/pay works)
from src.empresas.public_router import router as public_pay_router
api_router.include_router(public_pay_router)

app.include_router(api_router)

# Stripe webhook — mounted under /api/v1 so the erp.goeva.ai Vercel rewrite
# (`/api/v1/:path*` → backend) proxies it. Stripe is configured with the full
# `https://erp.goeva.ai/api/v1/webhooks/stripe` URL.
from src.webhooks.router import router as webhooks_router
app.include_router(webhooks_router, prefix="/api/v1")


def _liveness_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "eva-erp",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _check_db_connection(
    db_engine,
    label: str,
    *,
    timeout_seconds: float,
) -> tuple[bool, str | None]:
    async def _ping() -> None:
        async with db_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_ping(), timeout=timeout_seconds)
        return True, None
    except asyncio.TimeoutError:
        return False, f"{label} health check timed out after {timeout_seconds:.1f}s"
    except Exception as exc:
        return False, str(exc)[:200]


async def _db_health(timeout_seconds: float = 2.0) -> tuple[bool, str | None, bool, str | None]:
    erp_ok, erp_error = await _check_db_connection(
        engine,
        "ERP database",
        timeout_seconds=timeout_seconds,
    )

    eva_ok = False
    eva_error: str | None = None
    if eva_engine is not None:
        eva_ok, eva_error = await _check_db_connection(
            eva_engine,
            "Eva database",
            timeout_seconds=timeout_seconds,
        )
    return erp_ok, erp_error, eva_ok, eva_error


@app.get("/health/liveness")
async def health_liveness():
    return _liveness_payload()


@app.get("/health/readiness")
async def health_readiness():
    # Readiness MUST be cheap and side-effect-free. It only checks local DB
    # connectivity. Do NOT call run_live_checks here: that fans out to every
    # external monitoring target (FacturAPI, OpenAI, Supabase, etc.) and on
    # 2026-05-21 produced a 14,799/day loop against FacturAPI when combined
    # with the background monitor's self-referential `erp-api` check. The
    # background monitor (`monitoring_runner_loop`) is the only place that
    # should poll external APIs.
    erp_ok, erp_error, eva_ok, eva_error = await _db_health()
    db_ready = erp_ok and (eva_engine is None or eva_ok)

    payload = {
        "status": "ok" if db_ready else "error",
        "service": "eva-erp",
        "erp_db_connected": erp_ok,
        "erp_db_error": erp_error,
        "eva_db_configured": eva_engine is not None,
        "eva_db_connected": eva_ok if eva_engine is not None else None,
        "eva_db_error": eva_error if eva_engine is not None else None,
    }
    if not db_ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/health")
async def health():
    return _liveness_payload()
