
import json
import time
from typing import Any, Dict, List, Optional

from .base import AsyncBaseAdapter

try:
    from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition
    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False


class KafkaAdapter(AsyncBaseAdapter):
    def __init__(
        self,
        brokers: str = "localhost:9092",
        group_id: str = "log-collector-group",
        topics: Optional[List[str]] = None,
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = False,
        consumer_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__()
        self.brokers = brokers
        self.group_id = group_id
        self.topics = topics or []
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.consumer_config = consumer_config or {}
        
        self._consumer: Optional[Consumer] = None
        self._subscribed = False
    
    def _get_consumer(self) -> Consumer:
        if not HAS_KAFKA:
            raise ImportError("confluent-kafka is required for KafkaAdapter")
        
        if self._consumer is None:
            config = {
                "bootstrap.servers": self.brokers,
                "group.id": self.group_id,
                "auto.offset.reset": self.auto_offset_reset,
                "enable.auto.commit": self.enable_auto_commit,
                **self.consumer_config
            }
            self._consumer = Consumer(config)
            
            if self.topics:
                self._consumer.subscribe(self.topics)
                self._subscribed = True
        
        return self._consumer
    
    def subscribe(self, topics: List[str]) -> None:
        consumer = self._get_consumer()
        consumer.subscribe(topics)
        self.topics = topics
        self._subscribed = True
    
    def seek(self, offsets: Dict[str, Dict[int, int]]) -> None:
        consumer = self._get_consumer()
        partitions = []
        for topic, partition_offsets in offsets.items():
            for partition, offset in partition_offsets.items():
                tp = TopicPartition(topic, partition, offset)
                partitions.append(tp)
        consumer.assign(partitions)
    
    def get_offsets(self) -> Dict[str, Dict[int, int]]:
        if not self._consumer or not self._subscribed:
            return {}
        
        offsets: Dict[str, Dict[int, int]] = {}
        partitions = self._consumer.assignment()
        
        for tp in partitions:
            try:
                _, high = self._consumer.get_watermark_offsets(tp, cached=False)
                current = self._consumer.position([tp])[0].offset
                if tp.topic not in offsets:
                    offsets[tp.topic] = {}
                offsets[tp.topic][tp.partition] = current
            except Exception:
                pass
        
        return offsets
    
    def poll(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        consumer = self._get_consumer()
        msg = consumer.poll(timeout=timeout)
        
        if msg is None:
            return None
        
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None
            else:
                raise KafkaException(msg.error())
        
        try:
            value = msg.value().decode("utf-8")
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
            
            return {
                "topic": msg.topic(),
                "partition": msg.partition(),
                "offset": msg.offset(),
                "key": msg.key().decode("utf-8") if msg.key() else None,
                "value": value,
                "timestamp": msg.timestamp()
            }
        except Exception as e:
            print(f"Error parsing Kafka message: {e}")
            return None
    
    def commit(self, offsets: Optional[Dict[str, Dict[int, int]]] = None) -> None:
        consumer = self._get_consumer()
        if offsets:
            partitions = []
            for topic, partition_offsets in offsets.items():
                for partition, offset in partition_offsets.items():
                    tp = TopicPartition(topic, partition, offset)
                    partitions.append(tp)
            consumer.commit(offsets=partitions)
        else:
            consumer.commit()
    
    async def close(self) -> None:
        if not self._closed and self._consumer is not None:
            try:
                self._consumer.close()
            except Exception:
                pass
            self._consumer = None
            self._closed = True
