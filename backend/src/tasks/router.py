import re
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.tasks.models import Board, Task, TaskComment
from src.tasks.schemas import (
    BoardCreate,
    BoardResponse,
    BoardUpdate,
    CommentCreate,
    CommentResponse,
    TaskCreate,
    TaskDetailResponse,
    TaskResponse,
    TaskUpdate,
)

# ── Boards ──────────────────────────────────────────────
board_router = APIRouter(prefix="/boards", tags=["boards"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[\s_]+", "-", slug).strip("-")


@board_router.get("", response_model=list[BoardResponse])
async def list_boards(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Board).order_by(Board.created_at))
    return result.scalars().all()


@board_router.post("", response_model=BoardResponse, status_code=201)
async def create_board(
    data: BoardCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    slug = _slugify(data.name)
    existing = await db.execute(select(Board).where(Board.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    board = Board(name=data.name, slug=slug, description=data.description, created_by=user.id)
    db.add(board)
    await db.flush()
    await db.refresh(board)
    return board


@board_router.patch("/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: uuid.UUID,
    data: BoardUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Board).where(Board.id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(board, field, value)
    db.add(board)
    return board


@board_router.delete("/{board_id}")
async def delete_board(
    board_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Board).where(Board.id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    await db.delete(board)
    return {"message": "Board deleted"}


# ── Tasks ───────────────────────────────────────────────
router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status: Optional[str] = Query(None),
    board_id: Optional[uuid.UUID] = Query(None),
    assignee_id: Optional[uuid.UUID] = Query(None),
    priority: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Task).order_by(Task.created_at.desc())
    if status:
        q = q.where(Task.status == status)
    if board_id:
        q = q.where(Task.board_id == board_id)
    if assignee_id:
        q = q.where(Task.assignee_id == assignee_id)
    if priority:
        q = q.where(Task.priority == priority)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = Task(
        title=data.title,
        description=data.description,
        status=data.status,
        board_id=data.board_id,
        assignee_id=data.assignee_id,
        priority=data.priority,
        due_date=data.due_date,
        labels=data.labels,
        created_by=user.id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@router.get("/my-tasks", response_model=list[TaskResponse])
async def my_tasks(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task)
        .where(Task.assignee_id == user.id, Task.status != "done")
        .order_by(Task.due_date.asc().nullslast())
    )
    return result.scalars().all()


@router.get("/overdue", response_model=list[TaskResponse])
async def overdue_tasks(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    result = await db.execute(
        select(Task)
        .where(Task.due_date < today, Task.status != "done")
        .order_by(Task.due_date.asc())
    )
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id).options(selectinload(Task.comments))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    db.add(task)
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    return {"message": "Task deleted"}


@router.post("/{task_id}/comments", response_model=CommentResponse, status_code=201)
async def add_comment(
    task_id: uuid.UUID,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    comment = TaskComment(task_id=task_id, user_id=user.id, content=data.content)
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    return comment
