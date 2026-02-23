import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.common.config import settings
from src.common.database import engine, eva_engine
from src.eva_platform.monitoring_service import FAILURE_STATES, monitoring_runner_loop, run_live_checks


@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor_stop = asyncio.Event()
    monitor_task: asyncio.Task | None = None

    if settings.monitoring_enabled:
        monitor_task = asyncio.create_task(monitoring_runner_loop(monitor_stop))

    yield

    monitor_stop.set()
    if monitor_task is not None:
        monitor_task.cancel()
        try:
            await monitor_task
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
from src.vault.router import router as vault_router
from src.tasks.router import router as task_router
from src.tasks.router import board_router
from src.finances.router import router as finances_router
from src.kpis.router import router as kpis_router
from src.prospects.router import router as prospects_router
from src.meetings.router import router as meetings_router
from src.documents.router import router as documents_router
from src.okrs.router import router as okrs_router
from src.assistant.router import router as assistant_router
from src.facturas.router import router as facturas_router
from src.dashboard.router import router as dashboard_router
from src.eva_platform.router import router as eva_platform_router
from src.customers.router import router as customers_router
from src.agent.router import router as agent_router

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(notifications_router)
api_router.include_router(vault_router)
api_router.include_router(task_router)
api_router.include_router(board_router)
api_router.include_router(finances_router)
api_router.include_router(kpis_router)
api_router.include_router(prospects_router)
api_router.include_router(meetings_router)
api_router.include_router(documents_router)
api_router.include_router(okrs_router)
api_router.include_router(assistant_router)
api_router.include_router(facturas_router)
api_router.include_router(dashboard_router)
api_router.include_router(eva_platform_router)
api_router.include_router(customers_router)
api_router.include_router(agent_router)

app.include_router(api_router)


async def _db_health() -> tuple[bool, str | None, bool, str | None]:
    erp_ok = False
    erp_error = None
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            erp_ok = True
    except Exception as exc:
        erp_error = str(exc)[:200]

    eva_ok = False
    eva_error = None
    if eva_engine is not None:
        try:
            async with eva_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                eva_ok = True
        except Exception as exc:
            eva_error = str(exc)[:200]
    return erp_ok, erp_error, eva_ok, eva_error


@app.get("/health/liveness")
async def health_liveness():
    return {
        "status": "ok",
        "service": "eva-erp",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health/readiness")
async def health_readiness():
    erp_ok, erp_error, eva_ok, eva_error = await _db_health()
    check_results = await run_live_checks(exclude_check_keys={"erp-api"})
    readiness_check_keys = {"erp-db", "eva-db", "eva-api", "supabase-auth", "supabase-admin"}
    critical_results = [
        result for result in check_results if result.critical and result.check_key in readiness_check_keys
    ]
    failing_critical = [
        {
            "check_key": result.check_key,
            "service": result.service,
            "status": result.status,
            "error": result.error_message,
            "http_status": result.http_status,
        }
        for result in critical_results
        if result.status in FAILURE_STATES
    ]

    db_ready = erp_ok and (eva_engine is None or eva_ok)
    ready = db_ready and len(failing_critical) == 0

    return {
        "status": "ok" if ready else "error",
        "service": "eva-erp",
        "erp_db_connected": erp_ok,
        "erp_db_error": erp_error,
        "eva_db_configured": eva_engine is not None,
        "eva_db_connected": eva_ok if eva_engine is not None else None,
        "eva_db_error": eva_error if eva_engine is not None else None,
        "critical_checks": [
            {
                "check_key": result.check_key,
                "service": result.service,
                "status": result.status,
                "http_status": result.http_status,
                "error": result.error_message,
            }
            for result in critical_results
        ],
        "critical_failures": failing_critical,
    }


@app.get("/health")
async def health():
    erp_ok, erp_error, eva_ok, eva_error = await _db_health()
    status = "ok" if erp_ok and (eva_engine is None or eva_ok) else "error"
    return {
        "status": status,
        "service": "eva-erp",
        "erp_db_connected": erp_ok,
        "erp_db_error": erp_error,
        "eva_db_configured": eva_engine is not None,
        "eva_db_connected": eva_ok if eva_engine is not None else None,
        "eva_db_error": eva_error if eva_engine is not None else None,
    }
