
from typing import Any, Dict, List, Optional, Union

from .base import AsyncBaseAdapter

try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class RedisAdapter(AsyncBaseAdapter):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
        max_connections: int = 10,
        socket_timeout: Optional[float] = None,
        socket_connect_timeout: Optional[float] = None,
        **kwargs
    ):
        super().__init__()
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.decode_responses = decode_responses
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.kwargs = kwargs
        
        self._client = None
        self._pool = None

    def _get_client(self):
        if not HAS_REDIS:
            raise ImportError("redis-py is required for RedisAdapter")
        
        if self._client is None or self._client.connection is None:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=self.decode_responses,
                max_connections=self.max_connections,
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=self.socket_connect_timeout,
                **self.kwargs
            )
        return self._client

    async def set(
        self,
        name: str,
        value: Any,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
        keepttl: bool = False
    ):
        client = self._get_client()
        return await client.set(name, value, ex=ex, px=px, nx=nx, xx=xx, keepttl=keepttl)

    async def get(self, name: str) -> Optional[Any]:
        client = self._get_client()
        return await client.get(name)

    async def delete(self, *names: str) -> int:
        client = self._get_client()
        return await client.delete(*names)

    async def exists(self, *names: str) -> int:
        client = self._get_client()
        return await client.exists(*names)

    async def expire(self, name: str, time: int) -> bool:
        client = self._get_client()
        return await client.expire(name, time)

    async def ttl(self, name: str) -> int:
        client = self._get_client()
        return await client.ttl(name)

    async def hset(
        self,
        name: str,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        mapping: Optional[Dict[str, Any]] = None
    ) -> int:
        client = self._get_client()
        return await client.hset(name, key=key, value=value, mapping=mapping)

    async def hget(self, name: str, key: str) -> Optional[Any]:
        client = self._get_client()
        return await client.hget(name, key)

    async def hgetall(self, name: str) -> Dict[str, Any]:
        client = self._get_client()
        return await client.hgetall(name)

    async def hdel(self, name: str, *keys: str) -> int:
        client = self._get_client()
        return await client.hdel(name, *keys)

    async def lpush(self, name: str, *values: Any) -> int:
        client = self._get_client()
        return await client.lpush(name, *values)

    async def rpush(self, name: str, *values: Any) -> int:
        client = self._get_client()
        return await client.rpush(name, *values)

    async def lpop(self, name: str, count: Optional[int] = None) -> Optional[Any]:
        client = self._get_client()
        return await client.lpop(name, count=count)

    async def rpop(self, name: str, count: Optional[int] = None) -> Optional[Any]:
        client = self._get_client()
        return await client.rpop(name, count=count)

    async def lrange(self, name: str, start: int, end: int) -> List[Any]:
        client = self._get_client()
        return await client.lrange(name, start, end)

    async def llen(self, name: str) -> int:
        client = self._get_client()
        return await client.llen(name)

    async def sadd(self, name: str, *values: Any) -> int:
        client = self._get_client()
        return await client.sadd(name, *values)

    async def smembers(self, name: str) -> set:
        client = self._get_client()
        return await client.smembers(name)

    async def srem(self, name: str, *values: Any) -> int:
        client = self._get_client()
        return await client.srem(name, *values)

    async def zadd(
        self,
        name: str,
        mapping: Dict[str, float],
        nx: bool = False,
        xx: bool = False,
        ch: bool = False,
        gt: bool = False,
        lt: bool = False
    ) -> int:
        client = self._get_client()
        return await client.zadd(name, mapping, nx=nx, xx=xx, ch=ch, gt=gt, lt=lt)

    async def zrange(
        self,
        name: str,
        start: int,
        end: int,
        desc: bool = False,
        withscores: bool = False,
        bysocre: bool = False,
        bylex: bool = False,
        rev: bool = False,
        offset: Optional[int] = None,
        count: Optional[int] = None
    ) -> List[Any]:
        client = self._get_client()
        return await client.zrange(
            name,
            start,
            end,
            desc=desc,
            withscores=withscores,
            bysocre=bysocre,
            bylex=bylex,
            rev=rev,
            offset=offset,
            count=count
        )

    async def pipeline(self, transaction: bool = True):
        client = self._get_client()
        return client.pipeline(transaction=transaction)

    async def close(self):
        if not self._closed and self._client is not None:
            await self._client.aclose()
            self._client = None
            self._closed = True

