"""HTTP 采集器：通过 HTTP 请求获取数据。"""
from __future__ import annotations

from typing import Any

import aiohttp

from .base import BaseCollector, CollectorResult


class HttpCollector(BaseCollector):
    """发起 HTTP 请求并返回响应结果。

    config 字段：
        url (必填): 请求 URL
        method: GET / POST / PUT / DELETE / PATCH，默认 GET
        params: URL 查询参数 dict
        json: 请求体 JSON
        data: 表单数据 dict
        headers: 请求头 dict
        timeout: 超时秒数，默认 30
        max_retries: 最大重试次数，默认 3
        retry_delay: 重试间隔秒数(指数退避基数)，默认 1.0
        auth: {username, password} Basic Auth
        expect_json: 是否强制按 JSON 解析响应，默认 True
    """

    type_name = "http"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        if "url" not in config:
            raise ValueError("HttpCollector config: 'url' is required")
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=self.config.get("timeout", 30),
            )
            connector = aiohttp.TCPConnector(
                limit=self.config.get("pool_size", 10),
            )
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

    async def collect(self) -> CollectorResult:
        session = await self._ensure_session()
        method = (self.config.get("method") or "GET").upper()
        url = self.config["url"]
        params = self.config.get("params")
        json_data = self.config.get("json")
        form_data = self.config.get("data")
        headers = self.config.get("headers") or {}
        max_retries = int(self.config.get("max_retries", 3))
        retry_delay = float(self.config.get("retry_delay", 1.0))
        expect_json = bool(self.config.get("expect_json", True))

        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    data=form_data,
                    headers=headers,
                ) as resp:
                    resp.raise_for_status()
                    ctype = resp.headers.get("content-type", "")
                    if expect_json or "application/json" in ctype:
                        try:
                            data = await resp.json()
                        except Exception:
                            data = await resp.text()
                    else:
                        data = await resp.text()
                    return CollectorResult(data=data)
            except aiohttp.ClientError as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    import asyncio
                    backoff = retry_delay * (2 ** attempt)
                    await asyncio.sleep(backoff)
        assert last_exc is not None
        raise last_exc

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
