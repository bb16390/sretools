"""存储子包。"""
from .base import BaseStorage, StorageResult
from .database import DatabaseStorage
from .file import FileStorage
from .http import HttpStorage
from .kafka import KafkaStorage

__all__ = [
    "BaseStorage",
    "StorageResult",
    "DatabaseStorage",
    "FileStorage",
    "HttpStorage",
    "KafkaStorage",
]


_STORAGE_MAP = {
    "database": DatabaseStorage,
    "http": HttpStorage,
    "file": FileStorage,
    "kafka": KafkaStorage,
}


def get_storage(storage_type: str) -> type[BaseStorage]:
    try:
        return _STORAGE_MAP[storage_type]
    except KeyError as exc:
        raise ValueError(f"Unknown storage type: {storage_type}") from exc
