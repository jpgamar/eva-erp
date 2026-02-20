import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.notifications.models import Notification
from src.notifications.schemas import NotificationListResponse, NotificationResponse, UnreadCountResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    read: bool | None = Query(None, description="Filter by read status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Notification).where(Notification.user_id == current_user.id)
    count_query = select(func.count()).select_from(Notification).where(Notification.user_id == current_user.id)

    if read is not None:
        query = query.where(Notification.read == read)
        count_query = count_query.where(Notification.read == read)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    notifications = result.scalars().all()

    return NotificationListResponse(items=notifications, total=total)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id, Notification.read == False)
    )
    count = result.scalar()
    return UnreadCountResponse(count=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.read = True
    db.add(notification)
    return notification


@router.post("/mark-all-read")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.read == False)
        .values(read=True)
    )
    return {"message": "All notifications marked as read"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    await db.execute(delete(Notification).where(Notification.id == notification_id))
    return {"message": "Notification deleted"}
