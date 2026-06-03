
import re
from datetime import datetime
from typing import Any, Dict

from ..base import TransformScript


class FormatterScript(TransformScript):
    """数据格式化脚本"""

    @property
    def name(self) -> str:
        return "formatter"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        if isinstance(data, list):
            return [self._format_item(item, config) for item in data]
        elif isinstance(data, dict):
            return self._format_item(data, config)
        return data

    def _format_item(self, item: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """格式化单个字典项"""
        if not isinstance(item, dict):
            return item

        result = dict(item)

        if "rename" in config:
            for old_name, new_name in config["rename"].items():
                if old_name in result:
                    result[new_name] = result.pop(old_name)

        if "convert" in config:
            for field, conversion in config["convert"].items():
                if field in result:
                    result[field] = self._convert_type(result[field], conversion)

        if "format" in config:
            for field, fmt_str in config["format"].items():
                if field in result:
                    result[field] = self._format_value(result[field], fmt_str)

        if "round" in config:
            for field, decimals in config["round"].items():
                if field in result and isinstance(result[field], (int, float)):
                    result[field] = round(result[field], decimals)

        return result

    def _convert_type(self, value: Any, target_type: str) -> Any:
        """类型转换"""
        if target_type == "int":
            return int(value)
        elif target_type == "float":
            return float(value)
        elif target_type == "str":
            return str(value)
        elif target_type == "bool":
            return bool(value)
        elif target_type == "datetime":
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value
        return value

    def _format_value(self, value: Any, fmt_str: str) -> str:
        """格式化值"""
        if isinstance(value, datetime):
            return value.strftime(fmt_str)
        elif isinstance(value, (int, float)):
            return format(value, fmt_str)
        return str(value)


class RenameFieldsScript(TransformScript):
    """重命名字段脚本"""

    @property
    def name(self) -> str:
        return "rename"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return "mapping" in config and isinstance(config["mapping"], dict)

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        mapping = config["mapping"]

        if isinstance(data, list):
            return [
                {mapping.get(k, k): v for k, v in item.items()}
                if isinstance(item, dict) else item
                for item in data
            ]
        elif isinstance(data, dict):
            return {mapping.get(k, k): v for k, v in data.items()}

        return data


class DateFormatScript(TransformScript):
    """日期格式化脚本"""

    @property
    def name(self) -> str:
        return "date_format"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return "format" in config

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        fmt = config["format"]
        source_format = config.get("source_format")
        field = config.get("field")

        if isinstance(data, list):
            return [
                self._format_date(item, fmt, source_format, field)
                for item in data
            ]
        elif isinstance(data, dict):
            return self._format_date(data, fmt, source_format, field)

        return data

    def _format_date(self, item: Dict, fmt: str, source_format: str, field: str) -> Dict:
        """格式化日期字段"""
        if not isinstance(item, dict):
            return item

        result = dict(item)

        if field:
            if field in result:
                result[field] = self._parse_and_format(result[field], fmt, source_format)
        else:
            for k, v in result.items():
                if isinstance(v, str) and self._looks_like_date(v):
                    result[k] = self._parse_and_format(v, fmt, source_format)

        return result

    def _looks_like_date(self, value: str) -> bool:
        """检查是否像日期字符串"""
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",
            r"\d{4}/\d{2}/\d{2}",
            r"\d{2}-\d{2}-\d{4}",
        ]
        return any(re.match(p, value) for p in date_patterns)

    def _parse_and_format(self, value: str, fmt: str, source_format: str) -> str:
        """解析并格式化日期"""
        try:
            if source_format:
                dt = datetime.strptime(value, source_format)
            else:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime(fmt)
        except (ValueError, AttributeError):
            return value
