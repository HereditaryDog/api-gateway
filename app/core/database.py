import asyncio

from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import get_settings

settings = get_settings()
IS_SQLITE = "sqlite" in settings.DATABASE_URL


def is_sqlite_locked_error(exc: Exception) -> bool:
    if not IS_SQLITE or not isinstance(exc, OperationalError):
        return False
    return "database is locked" in str(exc).lower()


async def run_with_sqlite_retry(
    operation,
    *,
    session: AsyncSession | None = None,
    retries: int = 5,
    base_delay: float = 0.15,
):
    last_exc = None
    for attempt in range(retries):
        try:
            return await operation()
        except OperationalError as exc:
            if not is_sqlite_locked_error(exc):
                raise
            last_exc = exc
            if session is not None:
                await session.rollback()
            if attempt == retries - 1:
                raise
            await asyncio.sleep(base_delay * (attempt + 1))
    raise last_exc

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool if IS_SQLITE else None,
    connect_args={"timeout": 30} if IS_SQLITE else {},
)

if IS_SQLITE:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 声明基类
Base = declarative_base()


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库表"""
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_schema_updates(conn)


async def _ensure_schema_updates(conn):
    """为本地开发环境补齐历史表结构。"""
    if "sqlite" not in settings.DATABASE_URL:
        return

    result = await conn.exec_driver_sql("PRAGMA table_info(users)")
    columns = {row[1] for row in result.fetchall()}

    if "phone" not in columns:
        await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN phone VARCHAR(30)")
    if "email_verified" not in columns:
        await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0 NOT NULL")
