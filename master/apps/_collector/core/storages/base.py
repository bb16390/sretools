"""存储目的地抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StorageResult:
    """存储结果封装。"""
    success: bool = True
    message: str = ""
    rows_stored: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "rows_stored": self.rows_stored,
            "details": self.details,
        }


class BaseStorage(ABC):
    """存储目的地抽象基类。"""

    type_name: str = ""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    async def store(self, data: Any, *, task_id: str, log_id: int | None = None) -> StorageResult:
        """将采集到的数据写入目标存储。

        Args:
            data: 采集结果（CollectorResult.data）
            task_id: 所属采集任务ID
            log_id: 本次执行的日志ID（可选）
        """

    async def close(self) -> None:
        """资源清理，子类可覆盖。"""
