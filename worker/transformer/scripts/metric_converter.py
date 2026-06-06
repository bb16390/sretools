from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List


from ..base import TransformScript


class MetricConverterScript(TransformScript):
    """指标转换脚本"""

    @property
    def name(self) -> str:
        return "metric_converter"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True

    async def transform(self, data: Any, config: Dict[str, Any]) -> Any:
        if not isinstance(data, list):
            return data

        metrics = []
        metric_storage = defaultdict(list)

        for item in data:
            if isinstance(item, dict):
                converted_metrics = self._convert_item_to_metrics(item, config)
                metrics.extend(converted_metrics)

                for metric in converted_metrics:
                    metric_name = metric["name"]
                    labels = metric.get("labels", {})
                    key = (metric_name, tuple(sorted(labels.items())))
                    metric_storage[key].append({
                        "value": metric["value"],
                        "timestamp": metric.get("timestamp", datetime.now().timestamp())
                    })

        aggregated_metrics = self._aggregate_metrics(metric_storage, config)

        return aggregated_metrics

    def _convert_item_to_metrics(self, item: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        metrics = []

        timestamp = item.get("timestamp", datetime.now().timestamp())

        level = item.get("level", "INFO")
        source = item.get("source", "unknown")

        metrics.append({
            "name": "log_count",
            "value": 1,
            "labels": {"level": level, "source": source},
            "timestamp": timestamp
        })

        if "duration" in item:
            duration = item["duration"]
            if isinstance(duration, (int, float)):
                metrics.append({
                    "name": "processing_time",
                    "value": duration,
                    "labels": {"operation": item.get("operation", "unknown")},
                    "timestamp": timestamp
                })

        if "value" in item:
            value = item["value"]
            if isinstance(value, (int, float)):
                metric_name = item.get("name", "custom_metric")
                labels = item.get("labels", {})
                metrics.append({
                    "name": metric_name,
                    "value": value,
                    "labels": labels,
                    "timestamp": timestamp
                })

        return metrics

    def _aggregate_metrics(self, metric_storage: defaultdict, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        aggregated = []
        agg_ops = config.get("agg", ["sum", "count", "avg", "min", "max"])

        for (metric_name, labels_tuple), values in metric_storage.items():
            labels = dict(labels_tuple)
            numeric_values = [v["value"] for v in values if isinstance(v["value"], (int, float))]

            if numeric_values:
                for op in agg_ops:
                    agg_value = self._calculate_aggregation(numeric_values, op)
                    aggregated.append({
                        "name": metric_name,
                        "aggregation": op,
                        "value": agg_value,
                        "labels": labels,
                        "count": len(values)
                    })

        return aggregated

    def _calculate_aggregation(self, values: List[Any], operation: str) -> Any:
        if not values:
            return None

        if operation == "sum":
            return sum(values)
        elif operation == "count":
            return len(values)
        elif operation == "avg":
            return sum(values) / len(values)
        elif operation == "min":
            return min(values)
        elif operation == "max":
            return max(values)
        elif operation == "first":
            return values[0]
        elif operation == "last":
            return values[-1]

        return None
