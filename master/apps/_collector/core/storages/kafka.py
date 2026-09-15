"""Kafka 存储：将采集结果写入 Kafka 主题。"""
from __future__ import annotations

import json
from typing import Any

from .base import BaseStorage, StorageResult

try:
    from confluent_kafka import Producer  # type: ignore
    HAS_KAFKA = True
except ImportError:  # pragma: no cover
    HAS_KAFKA = False


class KafkaStorage(BaseStorage):
    """写入 Kafka。

    config 字段：
        bootstrap_servers (必填): Kafka brokers, e.g. "127.0.0.1:9092"
        topic (必填): 主题名
        key: 可选，固定的消息 key
        key_from_field: 从每行 dict 中取该字段作为 key（优先级高于 key）
        format: json / raw，默认 json
        flatten: data 为 list 时逐条发送（默认 True）；否则整体作为一条消息
        extra_producer_config: 附加的 librdkafka producer 配置
        flush_timeout: producer.flush 超时秒数，默认 10
    """

    type_name = "kafka"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        if not HAS_KAFKA:
            raise ImportError("confluent-kafka package is required for KafkaStorage")
        if "bootstrap_servers" not in config:
            raise ValueError("KafkaStorage config: 'bootstrap_servers' is required")
        if "topic" not in config:
            raise ValueError("KafkaStorage config: 'topic' is required")
        self._producer: Producer | None = None

    def _ensure_producer(self) -> Producer:
        if self._producer is None:
            cfg = {
                "bootstrap.servers": self.config["bootstrap_servers"],
                "acks": self.config.get("acks", "all"),
            }
            extra = self.config.get("extra_producer_config") or {}
            for k, v in extra.items():
                cfg[k] = v
            self._producer = Producer(cfg)
        return self._producer

    def _encode(self, item: Any) -> bytes:
        fmt = self.config.get("format", "json")
        if fmt == "json":
            return json.dumps(item, default=str, ensure_ascii=False).encode("utf-8")
        if isinstance(item, (bytes, bytearray)):
            return bytes(item)
        if isinstance(item, str):
            return item.encode("utf-8")
        return str(item).encode("utf-8")

    async def store(self, data: Any, *, task_id: str, log_id: int | None = None) -> StorageResult:
        producer = self._ensure_producer()
        topic = self.config["topic"]
        flatten = bool(self.config.get("flatten", True))

        messages: list[tuple[Any, bytes]] = []

        def _add(one: Any):
            key = None
            key_field = self.config.get("key_from_field")
            if key_field and isinstance(one, dict):
                key = one.get(key_field)
                if key is not None:
                    key = str(key).encode("utf-8")
            if key is None:
                fixed_key = self.config.get("key")
                if fixed_key is not None:
                    key = str(fixed_key).encode("utf-8")
            messages.append((key, self._encode(one)))

        if flatten and isinstance(data, list):
            for r in data:
                _add(r)
        else:
            _add(data)

        errors: list[str] = []
        delivered = 0

        def _on_delivery(err, msg):
            nonlocal delivered
            if err is not None:
                errors.append(str(err))
            else:
                delivered += 1

        for key, value in messages:
            try:
                producer.produce(topic=topic, key=key, value=value, on_delivery=_on_delivery)
            except BufferError:
                producer.poll(0)
                producer.produce(topic=topic, key=key, value=value, on_delivery=_on_delivery)
            producer.poll(0)

        flush_timeout = self.config.get("flush_timeout", 10)
        remaining = producer.flush(float(flush_timeout))
        success = not errors and remaining == 0
        return StorageResult(
            success=success,
            rows_stored=delivered,
            message="Kafka produced" if success else f"Kafka errors: {errors[:3]}; remaining={remaining}",
            details={
                "topic": topic,
                "sent": delivered,
                "total": len(messages),
                "remaining": remaining,
                "errors": errors[:10],
            },
        )

    async def close(self) -> None:
        if self._producer is not None:
            try:
                self._producer.flush(5)
            finally:
                self._producer = None
