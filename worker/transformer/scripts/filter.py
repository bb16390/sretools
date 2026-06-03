
import re
from typing import Any, Dict, List

from ..base import TransformScript


class FilterScript(TransformScript):
    """数据过滤脚本"""

    @property
    def name(self) -> str:
        return "filter"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        required = ["field", "operator", "value"]
        return all(k in config for k in required)

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        field = config["field"]
        operator = config["operator"]
        value = config["value"]

        if isinstance(data, list):
            return [
                item for item in data
                if self._matches(item, field, operator, value)
            ]
        elif isinstance(data, dict):
            return data if self._matches(data, field, operator, value) else None

        return data

    def _matches(self, item: Any, field: str, operator: str, value: Any) -> bool:
        """检查字段是否匹配条件"""
        if not isinstance(item, dict):
            return False

        field_value = self._get_field_value(item, field)
        if field_value is None:
            return False

        return self._compare(field_value, operator, value)

    def _get_field_value(self, item: Dict, field: str) -> Any:
        """获取字段值，支持嵌套字段（用 . 分隔）"""
        parts = field.split(".")
        current = item
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _compare(self, field_value: Any, operator: str, value: Any) -> bool:
        """比较操作"""
        operators = {
            "eq": lambda f, v: f == v,
            "ne": lambda f, v: f != v,
            "gt": lambda f, v: f > v,
            "ge": lambda f, v: f >= v,
            "lt": lambda f, v: f < v,
            "le": lambda f, v: f <= v,
            "contains": lambda f, v: v in f,
            "startswith": lambda f, v: isinstance(f, str) and f.startswith(v),
            "endswith": lambda f, v: isinstance(f, str) and f.endswith(v),
            "in": lambda f, v: f in v if isinstance(v, (list, tuple, set)) else f == v,
            "regex": lambda f, v: bool(re.search(v, str(f))) if isinstance(f, str) else False,
        }

        op_func = operators.get(operator)
        if op_func is None:
            raise ValueError(f"Unknown operator: {operator}")

        return op_func(field_value, value)


class ExcludeFieldsScript(TransformScript):
    """排除字段脚本"""

    @property
    def name(self) -> str:
        return "exclude_fields"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return "fields" in config and isinstance(config["fields"], list)

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        fields = config["fields"]

        if isinstance(data, list):
            return [
                {k: v for k, v in item.items() if k not in fields}
                if isinstance(item, dict) else item
                for item in data
            ]
        elif isinstance(data, dict):
            return {k: v for k, v in data.items() if k not in fields}

        return data


class PickFieldsScript(TransformScript):
    """选择字段脚本"""

    @property
    def name(self) -> str:
        return "pick_fields"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return "fields" in config and isinstance(config["fields"], list)

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        fields = config["fields"]

        if isinstance(data, list):
            return [
                {k: v for k, v in item.items() if k in fields}
                if isinstance(item, dict) else item
                for item in data
            ]
        elif isinstance(data, dict):
            return {k: v for k, v in data.items() if k in fields}

        return data
