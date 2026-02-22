"""Platform dashboard KPIs from Eva DB."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import eva_async_session, eva_engine, get_db
from src.eva_platform.drafts.models import AccountDraft
from src.eva_platform.models import EvaAccount, EvaMonitoringIssue, EvaPartner
from src.eva_platform.schemas import PlatformDashboardResponse

router = APIRouter()


@router.get("/dashboard", response_model=PlatformDashboardResponse)
async def platform_dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Defaults if Eva DB is not connected
    active_accounts = 0
    total_accounts = 0
    active_partners = 0
    open_issues = 0
    critical_issues = 0

    if eva_async_session is not None:
        async with eva_async_session() as eva_db:
            active_accounts = (await eva_db.execute(
                select(func.count(EvaAccount.id)).where(EvaAccount.is_active == True)
            )).scalar() or 0

            total_accounts = (await eva_db.execute(
                select(func.count(EvaAccount.id))
            )).scalar() or 0

            active_partners = (await eva_db.execute(
                select(func.count(EvaPartner.id)).where(EvaPartner.is_active == True)
            )).scalar() or 0

            open_issues = (await eva_db.execute(
                select(func.count(EvaMonitoringIssue.id)).where(
                    EvaMonitoringIssue.status.in_(["open", "acknowledged"])
                )
            )).scalar() or 0

            critical_issues = (await eva_db.execute(
                select(func.count(EvaMonitoringIssue.id)).where(
                    EvaMonitoringIssue.status.in_(["open", "acknowledged"]),
                    EvaMonitoringIssue.severity == "critical",
                )
            )).scalar() or 0

    # Drafts are in ERP DB
    draft_accounts_pending = (await db.execute(
        select(func.count(AccountDraft.id)).where(AccountDraft.status == "draft")
    )).scalar() or 0

    return PlatformDashboardResponse(
        active_accounts=active_accounts,
        total_accounts=total_accounts,
        active_partners=active_partners,
        open_issues=open_issues,
        critical_issues=critical_issues,
        draft_accounts_pending=draft_accounts_pending,
    )


@router.get("/health")
async def eva_platform_health(
    user: User = Depends(get_current_user),
):
    """Check Eva DB connectivity."""
    if eva_engine is None:
        return {"status": "not_configured", "detail": "EVA_DATABASE_URL not set"}

    try:
        async with eva_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
