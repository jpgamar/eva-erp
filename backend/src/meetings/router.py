import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.meetings.models import Meeting
from src.meetings.schemas import MeetingCreate, MeetingResponse, MeetingUpdate

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=list[MeetingResponse])
async def list_meetings(
    type: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Meeting).order_by(Meeting.date.desc())
    if type:
        q = q.where(Meeting.type == type)
    if search:
        q = q.where(Meeting.title.ilike(f"%{search}%"))
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    data: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    action_items_json = None
    if data.action_items:
        action_items_json = [item.model_dump(mode="json") for item in data.action_items]

    meeting = Meeting(
        title=data.title,
        date=data.date,
        duration_minutes=data.duration_minutes,
        type=data.type,
        attendees=data.attendees,
        notes_markdown=data.notes_markdown,
        action_items_json=action_items_json,
        prospect_id=data.prospect_id,
        customer_id=data.customer_id,
        created_by=user.id,
    )
    db.add(meeting)
    await db.flush()
    await db.refresh(meeting)
    return meeting


@router.get("/upcoming", response_model=list[MeetingResponse])
async def upcoming_meetings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    result = await db.execute(
        select(Meeting).where(Meeting.date > now).order_by(Meeting.date.asc())
    )
    return result.scalars().all()


@router.get("/recent", response_model=list[MeetingResponse])
async def recent_meetings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cutoff = datetime.utcnow() - timedelta(days=30)
    result = await db.execute(
        select(Meeting).where(Meeting.date >= cutoff).order_by(Meeting.date.desc())
    )
    return result.scalars().all()


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.patch("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: uuid.UUID,
    data: MeetingUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    update_data = data.model_dump(exclude_unset=True)
    if "action_items" in update_data:
        items = update_data.pop("action_items")
        if items is not None:
            meeting.action_items_json = [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in (data.action_items or [])]
        else:
            meeting.action_items_json = None

    for field, value in update_data.items():
        setattr(meeting, field, value)
    db.add(meeting)
    return meeting


@router.delete("/{meeting_id}")
async def delete_meeting(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    await db.delete(meeting)
    return {"message": "Meeting deleted"}
