
from typing import Any, Dict, List, Optional

from .base import AsyncBaseAdapter

try:
    import asynch
    from asynch.cursors import DictCursor
    HAS_ASYNCH = True
except ImportError:
    HAS_ASYNCH = False


class ClickHouseAdapter(AsyncBaseAdapter):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9000,
        database: str = "default",
        user: str = "default",
        password: str = "",
        pool_size: int = 5,
        pool_maxsize: int = 10,
        **kwargs
    ):
        super().__init__()
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool_size = pool_size
        self.pool_maxsize = pool_maxsize
        self.kwargs = kwargs
        
        self._pool = None
        self._connection = None

    async def _get_pool(self):
        if not HAS_ASYNCH:
            raise ImportError("asynch is required for ClickHouseAdapter")
        
        if self._pool is None:
            self._pool = await asynch.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                minsize=self.pool_size,
                maxsize=self.pool_maxsize,
                **self.kwargs
            )
        return self._pool

    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -&gt; List[Dict[str, Any]]:
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            async with conn.cursor(cursor=DictCursor) as cursor:
                await cursor.execute(sql, params or {})
                result = await cursor.fetchall()
                return list(result) if result else []

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
        data: List[Dict[str, Any]]
    ) -&gt; None:
        if not data:
            return
        
        columns = ', '.join(data[0].keys())
        placeholders = ', '.join(f'%({key})s' for key in data[0].keys())
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.executemany(sql, data)

    async def close(self):
        if not self._closed and self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._closed = True

