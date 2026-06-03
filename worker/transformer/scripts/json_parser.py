
import json
import re
from typing import Any, Dict, List, Optional

from ..base import TransformScript


class JsonParserScript(TransformScript):
    """JSON 解析脚本"""

    @property
    def name(self) -> str:
        return "json_parser"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        path = config.get("path")
        default = config.get("default", None)

        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return default

        if path:
            return self._extract_path(data, path)

        return data

    def _extract_path(self, data: Any, path: str) -> Any:
        """支持简单 JSONPath 提取"""
        if not path.startswith("$."):
            return data

        parts = path[2:].split(".")
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    index = int(part)
                    current = current[index] if 0 <= index < len(current) else None
                except ValueError:
                    return None
            else:
                return None

            if current is None:
                return None

        return current


class JsonDumpsScript(TransformScript):
    """JSON 序列化脚本"""

    @property
    def name(self) -> str:
        return "json_dumps"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True

    async def transform(self, data: Any, config: Dict[str, Any]) -> str:
        indent = config.get("indent", None)
        ensure_ascii = config.get("ensure_ascii", False)
        return json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
