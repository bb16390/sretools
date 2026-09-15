"""数据库采集器：通过 SQL 查询数据库。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .base import BaseCollector, CollectorResult


class DatabaseCollector(BaseCollector):
    """支持多种数据库（通过 SQLAlchemy async 驱动）。

    config 字段：
        url (必填): SQLAlchemy async URL, e.g.
            - sqlite+aiosqlite:///path/file.db
            - postgresql+asyncpg://user:pass@host/db
            - mysql+asyncmy://user:pass@host/db
            - clickhouse+asynch://user:pass@host/db
        query (必填): SQL 查询字符串
        queries (可选): 多条 SQL（执行全部，返回最后一条结果）
        echo: 是否打印 SQL 日志
        pool_size / max_overflow / pool_recycle: 连接池参数
    """

    type_name = "database"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        if "url" not in config:
            raise ValueError("DatabaseCollector config: 'url' is required")
        if "query" not in config and "queries" not in config:
            raise ValueError("DatabaseCollector config: 'query' or 'queries' is required")

        self._engine = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def _ensure_engine(self):
        if self._engine is None:
            self._engine = create_async_engine(
                self.config["url"],
                echo=self.config.get("echo", False),
                pool_size=self.config.get("pool_size", 5),
                max_overflow=self.config.get("max_overflow", 10),
                pool_recycle=self.config.get("pool_recycle", 3600),
            )
            self._session_factory = async_sessionmaker(
                self._engine, expire_on_commit=False, class_=AsyncSession,
            )

    async def collect(self) -> CollectorResult:
        self._ensure_engine()
        assert self._session_factory is not None

        queries = self.config.get("queries")
        if queries is None:
            queries = [self.config["query"]]
        elif isinstance(queries, str):
            queries = [queries]

        last_rows: list[dict[str, Any]] = []
        params = self.config.get("params") or {}

        async with self._session_factory() as session:
            for q in queries:
                result = await session.execute(text(q), params)
                await session.commit()
                if result.returns_rows:
                    rows = result.fetchall()
                    cols = list(result.keys())
                    last_rows = [dict(zip(cols, r)) for r in rows]

        return CollectorResult(data=last_rows)

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
