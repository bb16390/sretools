
import asyncio
from typing import Any, Dict, Optional

from .base import AsyncBaseAdapter

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


class HttpAdapter(AsyncBaseAdapter):
    def __init__(
        self,
        base_url: str = "",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        pool_size: int = 10,
        headers: Optional[Dict[str, str]] = None
    ):
        super().__init__()
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.pool_size = pool_size
        self.headers = headers or {}
        
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            connector = aiohttp.TCPConnector(limit=self.pool_size)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=self.headers
            )
        return self._session

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Any:
        if not HAS_AIOHTTP:
            raise ImportError("aiohttp is required for HttpAdapter")
        
        if self.base_url and not url.startswith(("http://", "https://")):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        
        session = await self._get_session()
        request_headers = {**self.headers, **(headers or {})}
        
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    data=data,
                    headers=request_headers,
                    **kwargs
                ) as response:
                    response.raise_for_status()
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        return await response.json()
                    else:
                        return await response.text()
            except aiohttp.ClientError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    raise last_exception

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Any:
        return await self._request("GET", url, params=params, headers=headers, **kwargs)

    async def post(
        self,
        url: str,
        json_data: Optional[Any] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Any:
        return await self._request(
            "POST",
            url,
            params=params,
            json_data=json_data,
            data=data,
            headers=headers,
            **kwargs
        )

    async def put(
        self,
        url: str,
        json_data: Optional[Any] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Any:
        return await self._request(
            "PUT",
            url,
            params=params,
            json_data=json_data,
            data=data,
            headers=headers,
            **kwargs
        )

    async def delete(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Any:
        return await self._request("DELETE", url, params=params, headers=headers, **kwargs)

    async def patch(
        self,
        url: str,
        json_data: Optional[Any] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Any:
        return await self._request(
            "PATCH",
            url,
            params=params,
            json_data=json_data,
            data=data,
            headers=headers,
            **kwargs
        )

    async def close(self):
        if not self._closed and self._session and not self._session.closed:
            await self._session.close()
            self._closed = True

