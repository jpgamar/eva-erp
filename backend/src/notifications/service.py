import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.notifications.models import Notification


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    link: str | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link=link,
    )
    db.add(notification)
    await db.flush()
    return notification
