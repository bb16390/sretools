
from typing import Any, Dict, List, Optional

from .base import AsyncBaseAdapter

try:
    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import SYNCHRONOUS
    from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
    HAS_INFLUXDB = True
except ImportError:
    HAS_INFLUXDB = False


class InfluxDBAdapter(AsyncBaseAdapter):
    def __init__(
        self,
        url: str = "http://localhost:8086",
        token: str = "",
        org: str = "",
        bucket: str = "",
        timeout: int = 30000,
        **kwargs
    ):
        super().__init__()
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.timeout = timeout
        self.kwargs = kwargs
        
        self._client = None
        self._write_api = None
        self._query_api = None
        self._delete_api = None

    async def _get_client(self):
        if not HAS_INFLUXDB:
            raise ImportError("influxdb-client is required for InfluxDBAdapter")
        
        if self._client is None:
            self._client = InfluxDBClientAsync(
                url=self.url,
                token=self.token,
                org=self.org,
                timeout=self.timeout,
                **self.kwargs
            )
        return self._client

    async def write_point(
        self,
        measurement: str,
        fields: Dict[str, Any],
        tags: Optional[Dict[str, str]] = None,
        bucket: Optional[str] = None,
        org: Optional[str] = None
    ):
        client = await self._get_client()
        
        point = Point(measurement)
        
        if tags:
            for key, value in tags.items():
                point = point.tag(key, value)
        
        for key, value in fields.items():
            point = point.field(key, value)
        
        write_api = client.write_api(write_options=SYNCHRONOUS)
        await write_api.write(
            bucket=bucket or self.bucket,
            org=org or self.org,
            record=point
        )

    async def write_points(
        self,
        points: List[Point],
        bucket: Optional[str] = None,
        org: Optional[str] = None
    ):
        client = await self._get_client()
        write_api = client.write_api(write_options=SYNCHRONOUS)
        await write_api.write(
            bucket=bucket or self.bucket,
            org=org or self.org,
            record=points
        )

    async def query(
        self,
        query: str,
        org: Optional[str] = None
    ) -&gt; List[Dict[str, Any]]:
        client = await self._get_client()
        query_api = client.query_api()
        tables = await query_api.query(
            query=query,
            org=org or self.org
        )
        
        results = []
        for table in tables:
            for record in table.records:
                results.append(record.values)
        return results

    async def query_data_frame(
        self,
        query: str,
        org: Optional[str] = None
    ):
        client = await self._get_client()
        query_api = client.query_api()
        return await query_api.query_data_frame(
            query=query,
            org=org or self.org
        )

    async def delete(
        self,
        start: str,
        stop: str,
        predicate: Optional[str] = None,
        bucket: Optional[str] = None,
        org: Optional[str] = None
    ):
        client = await self._get_client()
        delete_api = client.delete_api()
        await delete_api.delete(
            start=start,
            stop=stop,
            predicate=predicate,
            bucket=bucket or self.bucket,
            org=org or self.org
        )

    async def close(self):
        if not self._closed and self._client is not None:
            await self._client.close()
            self._client = None
            self._write_api = None
            self._query_api = None
            self._delete_api = None
            self._closed = True

