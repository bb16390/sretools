
from collections import defaultdict
from typing import Any, Dict, List

from ..base import TransformScript


class AggregatorScript(TransformScript):
    """数据聚合脚本"""

    @property
    def name(self) -> str:
        return "aggregator"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return "group_by" in config and "agg" in config

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        if not isinstance(data, list):
            return data

        group_by = config["group_by"]
        agg = config["agg"]
        having = config.get("having")

        groups: Dict[tuple, List[Dict]] = defaultdict(list)
        for item in data:
            if isinstance(item, dict):
                key = tuple(item.get(field) for field in group_by)
                groups[key].append(item)

        result = []
        for key, items in groups.items():
            result_item = dict(zip(group_by, key))

            for agg_field, agg_op in agg.items():
                values = [item.get(agg_field) for item in items if item.get(agg_field) is not None]
                result_item[agg_field] = self._aggregate(values, agg_op)

            if having and not self._check_having(result_item, having):
                continue

            result.append(result_item)

        return result

    def _aggregate(self, values: List[Any], operation: str) -> Any:
        """执行聚合操作"""
        if not values:
            return None

        numeric_values = [v for v in values if isinstance(v, (int, float))]
        if operation == "sum":
            return sum(numeric_values) if numeric_values else 0
        elif operation == "avg":
            return sum(numeric_values) / len(numeric_values) if numeric_values else 0
        elif operation == "count":
            return len(values)
        elif operation == "min":
            return min(values)
        elif operation == "max":
            return max(values)
        elif operation == "first":
            return values[0]
        elif operation == "last":
            return values[-1]

        return values

    def _check_having(self, item: Dict, having: Dict[str, Any]) -> bool:
        """检查 having 条件"""
        for field, condition in having.items():
            value = item.get(field)
            if value is None:
                return False

            if isinstance(condition, dict):
                op = condition.get("op", "eq")
                val = condition.get("value")
                if op == "gt":
                    return value > val
                elif op == "ge":
                    return value >= val
                elif op == "lt":
                    return value < val
                elif op == "le":
                    return value <= val
                elif op == "eq":
                    return value == val
                elif op == "ne":
                    return value != val

            return value == condition

        return True


class FlattenScript(TransformScript):
    """扁平化列表脚本"""

    @property
    def name(self) -> str:
        return "flatten"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        if not isinstance(data, list):
            return data

        max_depth = config.get("max_depth", -1)
        result = []
        self._flatten_to(data, result, max_depth, 0)
        return result

    def _flatten_to(self, items: List, result: List, max_depth: int, current_depth: int) -> None:
        """递归扁平化"""
        for item in items:
            if isinstance(item, list) and (max_depth < 0 or current_depth < max_depth):
                self._flatten_to(item, result, max_depth, current_depth + 1)
            else:
                result.append(item)


class UniqueScript(TransformScript):
    """去重脚本"""

    @property
    def name(self) -> str:
        return "unique"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        if not isinstance(data, list):
            return data

        key = config.get("key")
        if key:
            seen = set()
            result = []
            for item in data:
                if isinstance(item, dict):
                    item_key = item.get(key)
                else:
                    item_key = item
                if item_key not in seen:
                    seen.add(item_key)
                    result.append(item)
            return result
        else:
            seen = set()
            result = []
            for item in data:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
            return result
