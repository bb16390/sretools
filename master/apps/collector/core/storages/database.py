"""数据库存储：将采集结果写入目标数据库表。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any

from sqlalchemy import MetaData, String, Integer, Float, Boolean, DateTime, JSON as SAJSON, Text, Table, Column, insert, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .base import BaseStorage, StorageResult


def _infer_col_type(v: Any):
    if v is None:
        return String(512)
    if isinstance(v, bool):
        return Boolean()
    if isinstance(v, int):
        return Integer()
    if isinstance(v, float):
        return Float()
    if isinstance(v, datetime):
        return DateTime()
    if isinstance(v, (dict, list)):
        return SAJSON()
    return Text()


class DatabaseStorage(BaseStorage):
    """写入任意数据库表。

    config 字段：
        url (必填): SQLAlchemy async URL
        table (必填): 目标表名
        schema: 可选 schema
        create_if_missing: 表不存在时自动建表，默认 True
        mode: insert / upsert / replace，默认 insert
        unique_keys: 当 mode=upsert/replace 时，作为唯一键列名列表
        extra_fields: 写入时附加的固定字段 dict（如 task_id、采集时间等）
        batch_size: 批量写入大小，默认 500
        wrap_list: data 非 list 时是否包一层 list，默认 True
    """

    type_name = "database"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        if "url" not in config:
            raise ValueError("DatabaseStorage config: 'url' is required")
        if "table" not in config:
            raise ValueError("DatabaseStorage config: 'table' is required")
        self._engine = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._table: Table | None = None

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

    async def _ensure_table(self, sample: dict[str, Any]):
        assert self._engine is not None
        table_name = self.config["table"]
        schema = self.config.get("schema")
        metadata = MetaData(schema=schema)

        def _reflect_or_create(conn):
            try:
                metadata.reflect(bind=conn, only=[table_name], views=False)
            except Exception:
                pass
            if table_name in metadata.tables:
                self._table = metadata.tables[table_name]
                return
            if not self.config.get("create_if_missing", True):
                raise RuntimeError(f"Table {table_name} not found and create_if_missing=False")
            cols = [Column("id", Integer(), primary_key=True, autoincrement=True)]
            for k, v in sample.items():
                cols.append(Column(k, _infer_col_type(v), nullable=True))
            self._table = Table(table_name, metadata, *cols)
            metadata.create_all(bind=conn)

        async with self._engine.begin() as conn:
            await conn.run_sync(_reflect_or_create)

    async def store(self, data: Any, *, task_id: str, log_id: int | None = None) -> StorageResult:
        self._ensure_engine()
        assert self._session_factory is not None

        wrap_list = self.config.get("wrap_list", True)
        if wrap_list and not isinstance(data, list):
            rows = [data] if data is not None else []
        else:
            rows = list(data) if isinstance(data, (list, tuple)) else []
        if not rows:
            return StorageResult(success=True, message="No data to store", rows_stored=0)

        extra = self.config.get("extra_fields") or {}
        def _normalize(r: dict[str, Any]) -> dict[str, Any]:
            out = {**extra}
            if isinstance(r, dict):
                out.update(r)
            else:
                out.setdefault("value", r)
            if "task_id" not in out:
                out["task_id"] = task_id
            if log_id is not None and "collector_log_id" not in out:
                out["collector_log_id"] = log_id
            if "collected_at" not in out:
                out["collected_at"] = datetime.now()
            return out

        # 转 dict 列表
        normalized: list[dict[str, Any]] = []
        for r in rows:
            nr = r if isinstance(r, dict) else {"value": r}
            normalized.append(_normalize(nr))

        if self._table is None:
            await self._ensure_table(normalized[0])
        assert self._table is not None

        batch_size = int(self.config.get("batch_size", 500))
        mode = self.config.get("mode", "insert")
        unique_keys = self.config.get("unique_keys") or []

        total = 0
        async with self._session_factory() as session:
            for i in range(0, len(normalized), batch_size):
                batch = normalized[i:i + batch_size]
                if mode == "insert":
                    await session.execute(insert(self._table), batch)
                else:
                    dialect = self._engine.dialect.name
                    if dialect in ("mysql", "sqlite") and unique_keys:
                        for row in batch:
                            where = {k: row[k] for k in unique_keys if k in row}
                            if not where:
                                await session.execute(insert(self._table), [row])
                                continue
                            sel = self._table.select().where(
                                text(" AND ".join(f"{k}=:{k}" for k in where))
                            ).params(**where)
                            res = await session.execute(sel)
                            existing = res.first()
                            if existing:
                                if mode == "replace":
                                    upd = self._table.update().where(
                                        text(" AND ".join(f"{k}=:{k}" for k in where))
                                    ).params(**{**row, **where})
                                    await session.execute(upd)
                            else:
                                await session.execute(insert(self._table), [row])
                    else:
                        await session.execute(insert(self._table), batch)
                await session.commit()
                total += len(batch)

        return StorageResult(success=True, rows_stored=total, message="Stored successfully")

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._table = None
