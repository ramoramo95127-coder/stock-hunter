from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


async def database_ready(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False
