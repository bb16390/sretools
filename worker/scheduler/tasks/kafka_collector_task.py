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
    """偏移量管理器，支持本地文件系统保存，并通过 gRPC 上报到 master 端"""

    def __init__(
        self,
        task_id: str,
        grpc_client=None
    ):
        self.task_id = task_id
        self.grpc_client = grpc_client
        self._init_file_storage()

    def _init_file_storage(self):
        """初始化文件存储"""
        storage_dir = settings.local_storage_path
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)
        self._offset_file = os.path.join(storage_dir, f"kafka_offset_{self.task_id}.json")

    async def save_offsets(self, offsets: Dict[str, Dict[int, int]]):
        """保存偏移量到本地文件，并通过 gRPC 上报到 master

        Args:
            offsets: 格式为 {topic: {partition: offset}}
        """
        # 首先保存到本地文件
        await self._save_offsets_to_file(offsets)
        
        # 通过 gRPC 上报到 master
        if self.grpc_client:
            try:
                send_success = self.grpc_client.send_kafka_offsets(self.task_id, offsets)
                if not send_success:
                    logger.warning(f"Failed to send offsets to master via gRPC")
            except Exception as e:
                logger.error(f"Error sending offsets to master: {e}")

    async def _save_offsets_to_file(self, offsets: Dict[str, Dict[int, int]]):
        """保存偏移量到文件"""
        try:
            with open(self._offset_file, 'w', encoding='utf-8') as f:
                json.dump(offsets, f)
            logger.debug(f"Saved offsets to file: {self._offset_file}")
        except Exception as e:
            logger.error(f"Failed to save offsets to file: {e}")

    async def load_offsets(self) -> Dict[str, Dict[int, int]]:
        """加载偏移量

        Returns:
            格式为 {topic: {partition: offset}} 的字典
        """
        # 优先从 master 获取
        if self.grpc_client:
            try:
                master_offsets = self.grpc_client.get_kafka_offsets(self.task_id)
                if master_offsets:
                    logger.debug(f"Loaded offsets from master for task {self.task_id}")
                    return master_offsets
            except Exception as e:
                logger.error(f"Failed to load offsets from master: {e}")
        
        # 如果 master 获取失败，尝试从本地文件获取
        return await self._load_offsets_from_file()

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


class KafkaCollectorTask(BaseTask):
    """Kafka 消息收集任务

    Config fields:
        adapter_config (required): Dict of kwargs for KafkaAdapter constructor.
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
        grpc_client=None,
    ):
        super().__init__(task_type, config, task_id)
        self._validate_config()
        self._offset_manager = None
        self._transform_executor = TransformExecutor()
        self._grpc_client = grpc_client

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
        transform_task_id = self.config.get("transform_task_id")
        consume_timeout = self.config.get("consume_timeout", 1.0)
        max_records_per_batch = self.config.get("max_records_per_batch", 100)
        commit_interval = self.config.get("commit_interval", 5.0)

        from worker.adapter.kafka_adapter import KafkaAdapter

        loop = asyncio.new_event_loop()

        try:
            self._offset_manager = OffsetManager(
                task_id=self.task_id,
                grpc_client=self._grpc_client
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
