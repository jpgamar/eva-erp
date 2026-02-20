import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.database import Base


class Board(Base):
    __tablename__ = "boards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    columns: Mapped[list["Column"]] = relationship("Column", back_populates="board", order_by="Column.position")


class Column(Base):
    __tablename__ = "columns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("boards.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str] = mapped_column(String(7), default="#6b7280")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    board: Mapped["Board"] = relationship("Board", back_populates="columns")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="column", order_by="Task.position")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    column_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("columns.id", ondelete="CASCADE"))
    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("boards.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    labels: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    position: Mapped[float] = mapped_column(Float, default=0)
    source_meeting_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    column: Mapped["Column"] = relationship("Column", back_populates="tasks")
    comments: Mapped[list["TaskComment"]] = relationship("TaskComment", back_populates="task", order_by="TaskComment.created_at")


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["Task"] = relationship("Task", back_populates="comments")


class TaskActivity(Base):
    __tablename__ = "task_activities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
