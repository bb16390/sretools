
from typing import Any, Dict, List, Optional

from .base import AsyncBaseAdapter

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import text
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


class SqlAdapter(AsyncBaseAdapter):
    def __init__(
        self,
        url: str,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600
    ):
        super().__init__()
        self.url = url
        self.echo = echo
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        
        self._engine = None
        self._session_factory = None

    def _get_engine(self):
        if not HAS_SQLALCHEMY:
            raise ImportError("SQLAlchemy is required for SqlAdapter")
        
        if self._engine is None:
            self._engine = create_async_engine(
                self.url,
                echo=self.echo,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_timeout=self.pool_timeout,
                pool_recycle=self.pool_recycle
            )
        return self._engine

    def _get_session_factory(self):
        if self._session_factory is None:
            engine = self._get_engine()
            self._session_factory = async_sessionmaker(
                engine,
                expire_on_commit=False,
                class_=AsyncSession
            )
        return self._session_factory

    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -&gt; List[Dict[str, Any]]:
        session_factory = self._get_session_factory()
        
        async with session_factory() as session:
            result = await session.execute(text(sql), params or {})
            await session.commit()
            
            if result.returns_rows:
                rows = result.fetchall()
                columns = result.keys()
                return [dict(zip(columns, row)) for row in rows]
            return []

    async def fetch_one(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -&gt; Optional[Dict[str, Any]]:
        results = await self.execute(sql, params)
        return results[0] if results else None

    async def fetch_all(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -&gt; List[Dict[str, Any]]:
        return await self.execute(sql, params)

    async def insert(
        self,
        table: str,
        data: Dict[str, Any]
    ) -&gt; None:
        columns = ', '.join(data.keys())
        placeholders = ', '.join(f':{key}' for key in data.keys())
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        await self.execute(sql, data)

    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        where: str,
        where_params: Optional[Dict[str, Any]] = None
    ) -&gt; None:
        set_clause = ', '.join(f'{key} = :{key}' for key in data.keys())
        params = {**data, **(where_params or {})}
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        await self.execute(sql, params)

    async def delete(
        self,
        table: str,
        where: str,
        params: Optional[Dict[str, Any]] = None
    ) -&gt; None:
        sql = f"DELETE FROM {table} WHERE {where}"
        await self.execute(sql, params)

    async def close(self):
        if not self._closed and self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._closed = True

