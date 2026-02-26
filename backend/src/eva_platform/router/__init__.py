from fastapi import APIRouter

from src.eva_platform.router.accounts import router as accounts_router
from src.eva_platform.router.monitoring import router as monitoring_router
from src.eva_platform.router.partners import router as partners_router
from src.eva_platform.router.impersonation import router as impersonation_router
from src.eva_platform.router.dashboard import router as dashboard_router
from src.eva_platform.router.infrastructure import router as infrastructure_router

router = APIRouter(prefix="/eva-platform", tags=["eva-platform"])

router.include_router(accounts_router)
router.include_router(monitoring_router)
router.include_router(partners_router)
router.include_router(impersonation_router)
router.include_router(dashboard_router)
router.include_router(infrastructure_router)
