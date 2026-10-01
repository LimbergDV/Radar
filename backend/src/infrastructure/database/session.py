from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from src.infrastructure.database.models import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",  # Muestra queries en consola solo en dev
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependencia de FastAPI — inyecta una sesión por request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise