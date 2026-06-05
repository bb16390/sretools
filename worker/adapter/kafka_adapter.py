import logging
from typing import Any, Dict, List, Optional

from .base import AsyncBaseAdapter

try:
    from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition
    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False

logger = logging.getLogger(__name__)


class KafkaAdapter(AsyncBaseAdapter):
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        group_id: str = "default-group",
        topics: Optional[List[str]] = None,
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = False,
        auto_commit_interval_ms: int = 5000,
        session_timeout_ms: int = 30000,
        heartbeat_interval_ms: int = 10000,
        fetch_min_bytes: int = 1,
        fetch_max_wait_ms: int = 500,
        max_poll_records: int = 100,
        **kwargs
    ):
        super().__init__()
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topics = topics or []
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.auto_commit_interval_ms = auto_commit_interval_ms
        self.session_timeout_ms = session_timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.fetch_min_bytes = fetch_min_bytes
        self.fetch_max_wait_ms = fetch_max_wait_ms
        self.max_poll_records = max_poll_records
        self.kwargs = kwargs

        self._consumer = None
        self._subscribed = False

    def _get_consumer(self):
        if not HAS_KAFKA:
            raise ImportError("confluent-kafka is required for KafkaAdapter")

        if self._consumer is None:
            config = {
                "bootstrap.servers": self.bootstrap_servers,
                "group.id": self.group_id,
                "auto.offset.reset": self.auto_offset_reset,
                "enable.auto.commit": self.enable_auto_commit,
                "auto.commit.interval.ms": self.auto_commit_interval_ms,
                "session.timeout.ms": self.session_timeout_ms,
                "heartbeat.interval.ms": self.heartbeat_interval_ms,
                "fetch.min.bytes": self.fetch_min_bytes,
                "fetch.max.wait.ms": self.fetch_max_wait_ms,
                "max.poll.records": self.max_poll_records,
                **self.kwargs
            }
            self._consumer = Consumer(config)
            logger.info(f"Kafka consumer created for group: {self.group_id}")

        return self._consumer

    def _subscribe(self):
        if not self._subscribed and self.topics:
            consumer = self._get_consumer()
            consumer.subscribe(self.topics)
            self._subscribed = True
            logger.info(f"Subscribed to topics: {self.topics}")

    async def consume(
        self,
        timeout: float = 1.0,
        max_records: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if not HAS_KAFKA:
            raise ImportError("confluent-kafka is required for KafkaAdapter")

        consumer = self._get_consumer()
        self._subscribe()

        max_records = max_records or self.max_poll_records
        messages = []

        try:
            raw_messages = consumer.consume(
                num_messages=max_records,
                timeout=timeout
            )

            for msg in raw_messages:
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.info(f"Reached end of partition {msg.partition()}")
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        raise KafkaException(msg.error())
                else:
                    message = {
                        "value": msg.value(),
                        "key": msg.key(),
                        "topic": msg.topic(),
                        "partition": msg.partition(),
                        "offset": msg.offset(),
                        "timestamp": msg.timestamp()
                    }
                    messages.append(message)

            if messages:
                logger.debug(f"Consumed {len(messages)} messages from Kafka")

        except Exception as e:
            logger.error(f"Error consuming messages: {e}")
            raise

        return messages

    async def commit_offset(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        async_commit: bool = False
    ):
        if not HAS_KAFKA:
            raise ImportError("confluent-kafka is required for KafkaAdapter")

        consumer = self._get_consumer()

        try:
            if messages:
                offsets = []
                for msg in messages:
                    tp = TopicPartition(
                        msg["topic"],
                        msg["partition"],
                        msg["offset"] + 1
                    )
                    offsets.append(tp)
                consumer.commit(offsets=offsets, **{"async": async_commit})
                logger.debug(f"Committed offsets for {len(messages)} messages")
            else:
                consumer.commit(**{"async": async_commit})
                logger.debug("Committed current offsets")
        except Exception as e:
            logger.error(f"Error committing offset: {e}")
            raise

    async def close(self):
        if not self._closed and self._consumer is not None:
            try:
                self._consumer.close()
                logger.info("Kafka consumer closed")
            except Exception as e:
                logger.error(f"Error closing Kafka consumer: {e}")
            finally:
                self._consumer = None
                self._subscribed = False
                self._closed = True
