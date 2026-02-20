import re
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.tasks.models import Board, Column, Task, TaskActivity, TaskComment
from src.tasks.schemas import (
    BoardCreate,
    BoardDetailResponse,
    BoardResponse,
    BoardUpdate,
    ColumnCreate,
    ColumnResponse,
    ColumnUpdate,
    CommentCreate,
    CommentResponse,
    TaskCreate,
    TaskDetailResponse,
    TaskMove,
    TaskResponse,
    TaskUpdate,
)

router = APIRouter(prefix="/boards", tags=["tasks"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[\s_]+", "-", slug).strip("-")


DEFAULT_COLUMNS = [
    {"name": "To Do", "color": "#3b82f6", "position": 0},
    {"name": "In Progress", "color": "#f59e0b", "position": 1},
    {"name": "Done", "color": "#22c55e", "position": 2},
]


@router.get("", response_model=list[BoardResponse])
async def list_boards(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Board).order_by(Board.position))
    return result.scalars().all()


@router.post("", response_model=BoardResponse, status_code=201)
async def create_board(
    data: BoardCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    slug = _slugify(data.name)
    # Check slug uniqueness
    existing = await db.execute(select(Board).where(Board.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    board = Board(name=data.name, slug=slug, description=data.description, created_by=user.id)
    db.add(board)
    await db.flush()

    for col_data in DEFAULT_COLUMNS:
        db.add(Column(board_id=board.id, **col_data))

    await db.flush()
    await db.refresh(board)
    return board


@router.get("/{board_id}", response_model=BoardDetailResponse)
async def get_board(
    board_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Board)
        .where(Board.id == board_id)
        .options(selectinload(Board.columns).selectinload(Column.tasks))
    )
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


@router.patch("/{board_id}", response_model=BoardResponse)
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
    if data.name is not None:
        board.name = data.name
    if data.description is not None:
        board.description = data.description
    db.add(board)
    return board


@router.delete("/{board_id}")
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


@router.post("/{board_id}/columns", response_model=ColumnResponse, status_code=201)
async def create_column(
    board_id: uuid.UUID,
    data: ColumnCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Get max position
    result = await db.execute(
        select(Column).where(Column.board_id == board_id).order_by(Column.position.desc())
    )
    last = result.scalars().first()
    position = (last.position + 1) if last else 0

    col = Column(board_id=board_id, name=data.name, color=data.color, position=position)
    db.add(col)
    await db.flush()
    await db.refresh(col)
    return ColumnResponse(id=col.id, board_id=col.board_id, name=col.name, position=col.position, color=col.color, tasks=[])


@router.patch("/columns/{column_id}", response_model=ColumnResponse)
async def update_column(
    column_id: uuid.UUID,
    data: ColumnUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Column).where(Column.id == column_id))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Column not found")
    if data.name is not None: col.name = data.name
    if data.position is not None: col.position = data.position
    if data.color is not None: col.color = data.color
    db.add(col)
    return ColumnResponse(id=col.id, board_id=col.board_id, name=col.name, position=col.position, color=col.color, tasks=[])


@router.delete("/columns/{column_id}")
async def delete_column(
    column_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Column).where(Column.id == column_id))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Column not found")
    # Check for tasks
    tasks_result = await db.execute(select(Task).where(Task.column_id == column_id).limit(1))
    if tasks_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Column has tasks. Move or delete them first.")
    await db.delete(col)
    return {"message": "Column deleted"}


# Task endpoints — mounted on a separate router for cleaner paths
task_router = APIRouter(prefix="/tasks", tags=["tasks"])


@task_router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Get max position in column
    result = await db.execute(
        select(Task).where(Task.column_id == data.column_id).order_by(Task.position.desc())
    )
    last = result.scalars().first()
    position = (last.position + 1) if last else 0

    task = Task(
        board_id=data.board_id,
        column_id=data.column_id,
        title=data.title,
        description=data.description,
        assignee_id=data.assignee_id,
        priority=data.priority,
        due_date=data.due_date,
        labels=data.labels,
        position=position,
        created_by=user.id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@task_router.get("/{task_id}", response_model=TaskDetailResponse)
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


@task_router.patch("/{task_id}", response_model=TaskResponse)
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
        old = getattr(task, field)
        setattr(task, field, value)
        if old != value:
            db.add(TaskActivity(task_id=task.id, user_id=user.id, action=f"changed_{field}", old_value=str(old), new_value=str(value)))

    db.add(task)
    return task


@task_router.delete("/{task_id}")
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


@task_router.post("/{task_id}/move", response_model=TaskResponse)
async def move_task(
    task_id: uuid.UUID,
    data: TaskMove,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    old_column = task.column_id
    task.column_id = data.column_id
    task.position = data.position
    db.add(task)

    if old_column != data.column_id:
        db.add(TaskActivity(task_id=task.id, user_id=user.id, action="moved", old_value=str(old_column), new_value=str(data.column_id)))

    return task


@task_router.post("/{task_id}/comments", response_model=CommentResponse, status_code=201)
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


@task_router.get("/my-tasks", response_model=list[TaskResponse])
async def my_tasks(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task).where(Task.assignee_id == user.id).order_by(Task.due_date.asc().nullslast())
    )
    return result.scalars().all()


@task_router.get("/overdue", response_model=list[TaskResponse])
async def overdue_tasks(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    result = await db.execute(
        select(Task).where(Task.due_date < today).order_by(Task.due_date.asc())
    )
    return result.scalars().all()
