"""采集器基类定义。"""
from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from typing import Any

if sys.version_info >= (3, 11):
    pass
else:
    pass


class CollectorResult:
    """采集结果封装。"""

    def __init__(
        self,
        data: Any,
        rows_count: int | None = None,
        raw_size: int | None = None,
    ) -> None:
        self.data = data
        if rows_count is None:
            if isinstance(data, list):
                rows_count = len(data)
            elif data is None:
                rows_count = 0
            else:
                rows_count = 1
        self.rows_count = rows_count
        if raw_size is None:
            try:
                raw_size = len(json.dumps(data, default=str, ensure_ascii=False))
            except Exception:
                raw_size = 0
        self.raw_size = raw_size

    def sample(self, n: int = 3) -> Any:
        """取样例数据用于日志展示。"""
        if isinstance(self.data, list):
            return self.data[:n]
        return self.data


class BaseCollector(ABC):
    """采集器抽象基类。"""

    #: 采集器类型名称，子类必须覆盖
    type_name: str = ""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    async def collect(self) -> CollectorResult:
        """执行采集，返回采集结果。"""

    async def close(self) -> None:
        """资源清理，子类可覆盖。"""
