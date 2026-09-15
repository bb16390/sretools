"""采集器子包。"""
from .base import BaseCollector, CollectorResult
from .database import DatabaseCollector
from .http import HttpCollector
from .websocket import WebSocketCollector

__all__ = [
    "BaseCollector",
    "CollectorResult",
    "DatabaseCollector",
    "HttpCollector",
    "WebSocketCollector",
]


_COLLECTOR_MAP = {
    "database": DatabaseCollector,
    "http": HttpCollector,
    "websocket": WebSocketCollector,
}


def get_collector(collector_type: str) -> type[BaseCollector]:
    try:
        return _COLLECTOR_MAP[collector_type]
    except KeyError as exc:
        raise ValueError(f"Unknown collector type: {collector_type}") from exc
