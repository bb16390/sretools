"""HTTP 存储：通过 HTTP 回调把采集数据 POST 出去。"""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .base import BaseStorage, StorageResult


class HttpStorage(BaseStorage):
    """通过 HTTP 请求把数据推送到远端。

    config 字段：
        url (必填): 目标 URL
        method: POST / PUT / PATCH，默认 POST
        headers: 请求头 dict
        data_key: 把 data 作为该字段名放到 JSON body 中（为空则直接放 data）
        extra_body: 附加到 JSON body 的固定字段
        timeout: 超时秒数，默认 30
        max_retries: 最大重试次数，默认 3
        retry_delay: 重试间隔基数秒，默认 1.0
        batch_mode: 是否按 list 整体发送；False 时逐行发送，默认 True
        batch_size: 每批行数，batch_mode=True 时生效，默认 0（全部一次）
        auth: {username, password} Basic Auth
    """

    type_name = "http"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        if "url" not in config:
            raise ValueError("HttpStorage config: 'url' is required")
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.get("timeout", 30))
            connector = aiohttp.TCPConnector(limit=self.config.get("pool_size", 10))
            auth_cfg = self.config.get("auth")
            auth: aiohttp.BasicAuth | None = None
            if auth_cfg:
                auth = aiohttp.BasicAuth(
                    login=auth_cfg.get("username", ""),
                    password=auth_cfg.get("password", ""),
                )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=self.config.get("headers") or {},
                auth=auth,
            )
        return self._session

    async def _send_once(self, session: aiohttp.ClientSession, payload: Any) -> tuple[int, Any]:
        method = (self.config.get("method") or "POST").upper()
        url = self.config["url"]
        headers = self.config.get("headers") or {}
        max_retries = int(self.config.get("max_retries", 3))
        retry_delay = float(self.config.get("retry_delay", 1.0))

        data_key = self.config.get("data_key")
        extra_body = self.config.get("extra_body") or {}
        body: Any
        if data_key:
            body = {data_key: payload, **extra_body}
        elif isinstance(payload, dict) and isinstance(extra_body, dict):
            body = {**payload, **extra_body}
        else:
            body = payload

        last_exc: Exception | None = None
        last_text: str = ""
        for attempt in range(max_retries):
            try:
                async with session.request(
                    method=method, url=url, json=body, headers=headers,
                ) as resp:
                    last_text = await resp.text()
                    resp.raise_for_status()
                    try:
                        return resp.status, await resp.json()
                    except Exception:
                        return resp.status, last_text
            except aiohttp.ClientError as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
        assert last_exc is not None
        raise RuntimeError(f"HTTP storage failed after retries: {last_exc}; last_text={last_text[:500]}")

    async def store(self, data: Any, *, task_id: str, log_id: int | None = None) -> StorageResult:
        session = await self._ensure_session()

        if isinstance(data, list) and not self.config.get("batch_mode", True):
            rows = data
        else:
            rows = [data]

        batch_size = int(self.config.get("batch_size", 0) or 0)
        batches: list[Any] = []
        if batch_size > 0:
            for i in range(0, len(rows), batch_size):
                batches.append(rows[i:i + batch_size])
        else:
            batches.append(rows if len(rows) != 1 or self.config.get("batch_mode", True) else rows[0])

        rows_sent = 0
        last_details: Any = None
        for batch in batches:
            status, details = await self._send_once(session, batch)
            last_details = {"http_status": status, "details": details}
            if isinstance(batch, list):
                rows_sent += len(batch)
            else:
                rows_sent += 1

        return StorageResult(
            success=True, rows_stored=rows_sent,
            message=f"Sent {rows_sent} item(s) via HTTP",
            details=last_details or {},
        )

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
