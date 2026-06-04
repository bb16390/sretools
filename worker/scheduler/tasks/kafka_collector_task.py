import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from worker.adapter.base import AdapterManager
from worker.scheduler.base_task import BaseTask, ExecutionMode, TaskStatus
from worker.transformer.executor import TransformExecutor
from worker.core.settings import settings

logger = logging.getLogger(__name__)


class OffsetManager:
    """偏移量管理器，支持 Redis 或本地文件系统保存和读取消费偏移量"""

    def __init__(
        self,
        task_id: str,
        storage_type: str = "file",
        redis_config: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.storage_type = storage_type
        self.redis_config = redis_config or {}
        self._redis_adapter = None

        if storage_type == "file":
            self._init_file_storage()
        elif storage_type == "redis":
            self._init_redis_storage()
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")

    def _init_file_storage(self):
        """初始化文件存储"""
        storage_dir = settings.local_storage_path
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)
        self._offset_file = os.path.join(storage_dir, f"kafka_offset_{self.task_id}.json")

    def _init_redis_storage(self):
        """初始化 Redis 存储"""
        from worker.adapter.redis_adapter import RedisAdapter
        self._redis_adapter_cls = RedisAdapter

    def _get_redis_adapter(self):
        """获取 Redis 适配器实例"""
        if self._redis_adapter is None:
            self._redis_adapter = AdapterManager.get_or_create(
                self._redis_adapter_cls,
                self.redis_config
            )
        return self._redis_adapter

    async def save_offsets(self, offsets: Dict[str, Dict[int, int]]):
        """保存偏移量

        Args:
            offsets: 格式为 {topic: {partition: offset}}
        """
        if self.storage_type == "file":
            await self._save_offsets_to_file(offsets)
        elif self.storage_type == "redis":
            await self._save_offsets_to_redis(offsets)

    async def _save_offsets_to_file(self, offsets: Dict[str, Dict[int, int]]):
        """保存偏移量到文件"""
        try:
            with open(self._offset_file, 'w', encoding='utf-8') as f:
                json.dump(offsets, f)
            logger.debug(f"Saved offsets to file: {self._offset_file}")
        except Exception as e:
            logger.error(f"Failed to save offsets to file: {e}")

    async def _save_offsets_to_redis(self, offsets: Dict[str, Dict[int, int]]):
        """保存偏移量到 Redis"""
        try:
            redis_adapter = self._get_redis_adapter()
            key = f"kafka:offset:{self.task_id}"
            await redis_adapter.set(key, json.dumps(offsets))
            logger.debug(f"Saved offsets to Redis with key: {key}")
        except Exception as e:
            logger.error(f"Failed to save offsets to Redis: {e}")

    async def load_offsets(self) -> Dict[str, Dict[int, int]]:
        """加载偏移量

        Returns:
            格式为 {topic: {partition: offset}} 的字典
        """
        if self.storage_type == "file":
            return await self._load_offsets_from_file()
        elif self.storage_type == "redis":
            return await self._load_offsets_from_redis()
        return {}

    async def _load_offsets_from_file(self) -> Dict[str, Dict[int, int]]:
        """从文件加载偏移量"""
        try:
            if os.path.exists(self._offset_file):
                with open(self._offset_file, 'r', encoding='utf-8') as f:
                    offsets = json.load(f)
                logger.debug(f"Loaded offsets from file: {self._offset_file}")
                return {topic: {int(p): o for p, o in parts.items()} for topic, parts in offsets.items()}
        except Exception as e:
            logger.error(f"Failed to load offsets from file: {e}")
        return {}

    async def _load_offsets_from_redis(self) -> Dict[str, Dict[int, int]]:
        """从 Redis 加载偏移量"""
        try:
            redis_adapter = self._get_redis_adapter()
            key = f"kafka:offset:{self.task_id}"
            value = await redis_adapter.get(key)
            if value:
                offsets = json.loads(value)
                logger.debug(f"Loaded offsets from Redis with key: {key}")
                return {topic: {int(p): o for p, o in parts.items()} for topic, parts in offsets.items()}
        except Exception as e:
            logger.error(f"Failed to load offsets from Redis: {e}")
        return {}


class KafkaCollectorTask(BaseTask):
    """Kafka 消息收集任务

    Config fields:
        adapter_config (required): Dict of kwargs for KafkaAdapter constructor.
        offset_storage (optional): Storage type for offsets, "file" or "redis", default "file".
        offset_redis_config (optional): Redis config for offset storage if offset_storage is "redis".
        transform_task_id (optional): Task ID for data transformation.
        consume_timeout (optional): Timeout for Kafka consume in seconds, default 1.0.
        max_records_per_batch (optional): Max records to consume per batch, default 100.
        commit_interval (optional): Interval to commit offsets in seconds, default 5.0.
    """

    def __init__(
        self,
        task_type: str,
        config: Dict[str, Any],
        task_id: str = None,
    ):
        super().__init__(task_type, config, task_id)
        self._validate_config()
        self._offset_manager = None
        self._transform_executor = TransformExecutor()

    def _validate_config(self):
        """验证配置"""
        required_fields = ["adapter_config"]
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required config field: {field}")

    def _default_execution_mode(self) -> ExecutionMode:
        return ExecutionMode.THREAD

    def _run(self):
        """核心执行逻辑"""
        adapter_config = self.config["adapter_config"]
        offset_storage = self.config.get("offset_storage", "file")
        offset_redis_config = self.config.get("offset_redis_config", {})
        transform_task_id = self.config.get("transform_task_id")
        consume_timeout = self.config.get("consume_timeout", 1.0)
        max_records_per_batch = self.config.get("max_records_per_batch", 100)
        commit_interval = self.config.get("commit_interval", 5.0)

        from worker.adapter.kafka_adapter import KafkaAdapter

        loop = asyncio.new_event_loop()

        try:
            self._offset_manager = OffsetManager(
                task_id=self.task_id,
                storage_type=offset_storage,
                redis_config=offset_redis_config
            )

            adapter = AdapterManager.get_or_create(KafkaAdapter, adapter_config)

            logger.info(
                "KafkaCollectorTask[%s] started. Storage: %s",
                self.task_id, offset_storage,
            )

            last_commit_time = time.time()
            processed_messages = []

            while not self._stop_event.is_set():
                if self._pause_event is not None and not self._pause_event.is_set():
                    self._pause_event.wait(timeout=1)
                    continue

                start_time = time.time()
                try:
                    messages = loop.run_until_complete(
                        adapter.consume(
                            timeout=consume_timeout,
                            max_records=max_records_per_batch
                        )
                    )

                    if messages:
                        processed_data = messages

                        if transform_task_id:
                            processed_data = loop.run_until_complete(
                                self._transform_executor.execute(
                                    task_id=transform_task_id,
                                    data=messages
                                )
                            )

                        processed_messages.extend(messages)

                        duration_ms = (time.time() - start_time) * 1000
                        self._notify_status("success", result=processed_data, duration_ms=duration_ms)
                        logger.debug(
                            "KafkaCollectorTask[%s] processed %d messages. Duration: %.2fms",
                            self.task_id, len(messages), duration_ms,
                        )

                    current_time = time.time()
                    if (current_time - last_commit_time) >= commit_interval and processed_messages:
                        offsets = self._extract_offsets(processed_messages)
                        loop.run_until_complete(self._offset_manager.save_offsets(offsets))
                        loop.run_until_complete(adapter.commit_offset(messages=processed_messages))
                        processed_messages = []
                        last_commit_time = current_time

                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    self._notify_status("failed", result=str(e), duration_ms=duration_ms)
                    logger.error(
                        "KafkaCollectorTask[%s] error: %s",
                        self.task_id, e,
                    )

                self._stop_event.wait(timeout=0.1)

        finally:
            if processed_messages:
                try:
                    offsets = self._extract_offsets(processed_messages)
                    loop.run_until_complete(self._offset_manager.save_offsets(offsets))
                except Exception as e:
                    logger.error(f"Failed to save final offsets: {e}")
            loop.close()
            logger.info("KafkaCollectorTask[%s] stopped.", self.task_id)

    def _extract_offsets(self, messages: List[Dict[str, Any]]) -> Dict[str, Dict[int, int]]:
        """从消息中提取偏移量"""
        offsets = {}
        for msg in messages:
            topic = msg["topic"]
            partition = msg["partition"]
            offset = msg["offset"]
            if topic not in offsets:
                offsets[topic] = {}
            if partition not in offsets[topic] or offset > offsets[topic][partition]:
                offsets[topic][partition] = offset
        return offsets
