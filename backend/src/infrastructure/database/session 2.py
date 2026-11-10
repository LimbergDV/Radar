"""Engine y session factory de SQLAlchemy async.

`get_db` (la dependencia que entrega una sesion por request) vive en
`src/presentation/dependencies.py`: es una pieza de FastAPI, no de infraestructura.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.database.settings import settings

engine = create_async_engine(
    settings.database_url,
    # Echo solo en desarrollo, y sin el ruido de las sentencias internas.
    echo=settings.app_env == "development" and settings.sql_echo,
    pool_pre_ping=True,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def dispose_engine() -> None:
    """Cierra el pool de conexiones (para el apagado de la app)."""
    await engine.dispose()


__all__ = ["engine", "AsyncSessionLocal", "AsyncSession", "dispose_engine"]