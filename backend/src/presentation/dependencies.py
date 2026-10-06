"""Dependencias de FastAPI (inyeccion de dependencias)."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import AsyncSessionLocal


async def get_db() -> AsyncIterator[AsyncSession]:
    """Una sesion por request, con commit automatico al salir."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise