from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.common.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


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
from src.customers.router import router as customers_router
from src.kpis.router import router as kpis_router
from src.prospects.router import router as prospects_router
from src.meetings.router import router as meetings_router
from src.documents.router import router as documents_router
from src.okrs.router import router as okrs_router
from src.assistant.router import router as assistant_router
from src.facturas.router import router as facturas_router
from src.dashboard.router import router as dashboard_router
from src.eva_platform.router import router as eva_platform_router

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(notifications_router)
api_router.include_router(vault_router)
api_router.include_router(task_router)
api_router.include_router(board_router)
api_router.include_router(finances_router)
api_router.include_router(customers_router)
api_router.include_router(kpis_router)
api_router.include_router(prospects_router)
api_router.include_router(meetings_router)
api_router.include_router(documents_router)
api_router.include_router(okrs_router)
api_router.include_router(assistant_router)
api_router.include_router(facturas_router)
api_router.include_router(dashboard_router)
api_router.include_router(eva_platform_router)

app.include_router(api_router)


@app.get("/health")
async def health():
    from src.common.database import eva_engine
    eva_ok = False
    eva_error = None
    if eva_engine:
        try:
            from sqlalchemy import text
            async with eva_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                eva_ok = True
        except Exception as exc:
            eva_error = str(exc)[:200]
    return {
        "status": "ok",
        "service": "eva-erp",
        "eva_db_configured": eva_engine is not None,
        "eva_db_connected": eva_ok,
        "eva_db_error": eva_error,
    }
