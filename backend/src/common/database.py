from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.common.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    connect_args={"statement_cache_size": 0},
    pool_size=5,
    max_overflow=10,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class EvaBase(DeclarativeBase):
    """Separate base for Eva production DB mirror models.

    Alembic only targets Base.metadata, so EvaBase tables are never
    created/modified by ERP migrations.
    """
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Eva production DB (read/write for platform management) ──────────

eva_engine = None
eva_async_session = None

if settings.eva_database_url:
    eva_engine = create_async_engine(
        settings.eva_database_url,
        echo=False,
        connect_args={"statement_cache_size": 0},
        pool_size=3,
        max_overflow=5,
    )
    eva_async_session = async_sessionmaker(eva_engine, class_=AsyncSession, expire_on_commit=False)


async def get_eva_db() -> AsyncSession:
    """Dependency for Eva production DB sessions."""
    if eva_async_session is None:
        raise RuntimeError("Eva database not configured. Set EVA_DATABASE_URL in .env")
    async with eva_async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
