"""
gRPC Server implementation for Master - Worker Communication.
This runs in parallel with the existing HTTP/REST API.
"""

import json
import queue
import time
import grpc
import threading
from concurrent import futures
from typing import Any, Dict, List, Optional

try:
    from master.core.settings import settings
    from master.core.security import verify_signature, SECRET_KEY
except ImportError:
    # Fallback if not running in the full project context
    SECRET_KEY = "test-secret-key"

from . import worker_pb2
from . import worker_pb2_grpc


# In-memory storage (shared with HTTP API if needed)
workers: Dict[str, Dict[str, Any]] = {}
worker_connections: Dict[str, Any] = {}  # For bidirectional streaming
kafka_offsets: Dict[str, Dict[str, Any]] = {}  # {worker_id: {task_id: offsets_data}}

# Default worker config
worker_config = {
    "log_collect_interval": "5",
    "log_batch_size": "1000",
    "log_queue_size": "10000",
    "metric_collect_interval": "10",
    "metric_batch_size": "500"
}


class WorkerServiceServicer(worker_pb2_grpc.WorkerServiceServicer):
    """Implementation of WorkerService gRPC."""

    def __init__(self):
        # Bidirectional stream state：
        #   worker_id -> {"queue": queue.Queue, "context": grpc.ServicerContext}
        # 当 worker 通过 Communicate 流上线后，会在此注册一个消息队列；
        # master 端通过 push_task_update / push_master_message 写入队列，
        # Communicate 方法从队列读取并 yield 给 worker。
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self._streams_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Communicate 流辅助方法（供 TaskDispatcher 调用）
    # ------------------------------------------------------------------
    def is_worker_connected(self, worker_id: str) -> bool:
        """判断指定 worker 是否已建立 Communicate 流。"""
        with self._streams_lock:
            stream_info = self.active_streams.get(worker_id)
        return stream_info is not None and stream_info.get("context").is_active()

    def push_master_message(self, worker_id: str, master_msg) -> bool:
        """向指定 worker 的 Communicate 流队列写入一条 MasterMessage。"""
        with self._streams_lock:
            stream_info = self.active_streams.get(worker_id)
        if stream_info is None:
            return False
        if not stream_info.get("context").is_active():
            return False
        try:
            stream_info["queue"].put_nowait(master_msg)
            return True
        except queue.Full:
            print(f"[gRPC] message queue full for worker {worker_id}")
            return False

    def push_task_update(
        self,
        worker_id: str,
        task_id: str,
        action: str,
        task_type: str,
        config: Dict[str, Any],
    ) -> bool:
        """构造 TaskUpdate 并推送到 worker。"""
        # proto 的 TaskUpdate.config 是 map<string,string>，需要把
        # 复杂的 worker_config 序列化为 JSON 字符串放在统一 key 下，
        # worker 端从 "config_json" 反序列化。
        config_map = {"config_json": json.dumps(config, ensure_ascii=False, default=str)}
        task_update = worker_pb2.TaskUpdate(
            task_id=task_id,
            action=action,
            task_type=task_type,
            config=config_map,
            timestamp=time.time(),
        )
        master_msg = worker_pb2.MasterMessage(task_update=task_update)
        return self.push_master_message(worker_id, master_msg)

    def _register_stream(self, worker_id: str, context) -> queue.Queue:
        """注册一条 Communicate 流，返回该 worker 的消息队列。

        若同一 worker 上线多次，旧流会被标记为不活跃（context 取消）。
        """
        msg_queue: queue.Queue = queue.Queue(maxsize=1024)
        with self._streams_lock:
            old = self.active_streams.get(worker_id)
            if old is not None:
                try:
                    old["context"].cancel()
                except Exception:
                    pass
            self.active_streams[worker_id] = {
                "queue": msg_queue,
                "context": context,
            }
        print(f"[gRPC] Communicate stream registered for worker {worker_id}")
        return msg_queue

    def _unregister_stream(self, worker_id: str, msg_queue: queue.Queue) -> None:
        """注销 Communicate 流。"""
        with self._streams_lock:
            current = self.active_streams.get(worker_id)
            # 仅在队列仍属于当前流时才移除（避免误删新流）
            if current is not None and current.get("queue") is msg_queue:
                del self.active_streams[worker_id]
        print(f"[gRPC] Communicate stream closed for worker {worker_id}")

    # ------------------------------------------------------------------
    # 原有 RPC：注册 / 心跳 / 日志 / 指标 / 配置 / 健康检查
    # ------------------------------------------------------------------
    def RegisterWorker(self, request, context):
        """Register a worker with the master."""
        # Verify signature
        data_to_verify = {
            "worker_id": request.worker_id,
            "info": {
                "version": request.info.version,
                "host": request.info.host,
                "port": request.info.port,
                "timestamp": request.info.timestamp
            }
        }

        if not verify_signature(data_to_verify, request.signature, SECRET_KEY):
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details("Invalid signature")
            return worker_pb2.RegisterResponse(
                success=False,
                message="Invalid signature",
                worker_id="",
                config={},
                timestamp=time.time()
            )

        # Register worker
        worker_id = request.worker_id
        workers[worker_id] = {
            "worker_id": worker_id,
            "status": "online",
            "last_registered": time.time(),
            "last_heartbeat": time.time(),
            "info": {
                "version": request.info.version,
                "host": request.info.host,
                "port": request.info.port
            }
        }

        print(f"[gRPC] Worker {worker_id} registered successfully")

        return worker_pb2.RegisterResponse(
            success=True,
            message="Worker registered successfully",
            worker_id=worker_id,
            config=worker_config,
            timestamp=time.time()
        )

    def SendHeartbeat(self, request, context):
        """Process heartbeat from worker."""
        # Verify signature
        data_to_verify = {
            "worker_id": request.worker_id,
            "status": request.status,
            "timestamp": request.timestamp
        }

        if not verify_signature(data_to_verify, request.signature, SECRET_KEY):
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details("Invalid signature")
            return worker_pb2.HeartbeatResponse(
                success=False,
                message="Invalid signature",
                timestamp=time.time()
            )

        worker_id = request.worker_id
        if worker_id not in workers:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Worker not registered")
            return worker_pb2.HeartbeatResponse(
                success=False,
                message="Worker not registered",
                timestamp=time.time()
            )

        # Update worker status
        workers[worker_id]["last_heartbeat"] = time.time()
        workers[worker_id]["status"] = request.status

        print(f"[gRPC] Heartbeat from worker {worker_id}")

        return worker_pb2.HeartbeatResponse(
            success=True,
            message="Heartbeat received",
            timestamp=time.time()
        )

    def SendLogs(self, request_iterator, context):
        """Receive logs from worker (client streaming)."""
        received_count = 0
        worker_id = None

        try:
            for log_entry in request_iterator:
                if worker_id is None:
                    worker_id = log_entry.worker_id

                received_count += 1
                # Here you would process/store the log
                print(f"[gRPC] Log from {log_entry.worker_id}: [{log_entry.level}] {log_entry.message}")

        except Exception as e:
            print(f"[gRPC] Error receiving logs: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))

        return worker_pb2.SendLogsResponse(
            success=True,
            message=f"Received {received_count} logs",
            received_count=received_count,
            timestamp=time.time()
        )

    def SendMetrics(self, request_iterator, context):
        """Receive metrics from worker (client streaming)."""
        received_count = 0
        worker_id = None

        try:
            for metric_entry in request_iterator:
                if worker_id is None:
                    worker_id = metric_entry.worker_id

                received_count += 1
                # Here you would process/store the metric
                print(f"[gRPC] Metric from {metric_entry.worker_id}: {metric_entry.name} = {metric_entry.value} {metric_entry.unit}")

        except Exception as e:
            print(f"[gRPC] Error receiving metrics: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))

        return worker_pb2.SendMetricsResponse(
            success=True,
            message=f"Received {received_count} metrics",
            received_count=received_count,
            timestamp=time.time()
        )

    def GetConfig(self, request, context):
        """Get configuration for worker."""
        print(f"[gRPC] Config requested by worker {request.worker_id}")

        return worker_pb2.GetConfigResponse(
            success=True,
            config=worker_config,
            timestamp=time.time()
        )

    def HealthCheck(self, request, context):
        """Health check."""
        return worker_pb2.HealthCheckResponse(
            status=worker_pb2.HealthCheckResponse.SERVING,
            timestamp=time.time()
        )

    def SendKafkaOffsets(self, request, context):
        """Receive Kafka offsets from worker and store them."""
        try:
            # Verify signature
            data_to_verify = {
                "worker_id": request.worker_id,
                "task_id": request.task_id,
                "timestamp": request.timestamp
            }

            if not verify_signature(data_to_verify, request.signature, SECRET_KEY):
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Invalid signature")
                return worker_pb2.SendKafkaOffsetsResponse(
                    success=False,
                    message="Invalid signature",
                    timestamp=time.time()
                )

            # Store offsets
            worker_id = request.worker_id
            task_id = request.task_id

            if worker_id not in kafka_offsets:
                kafka_offsets[worker_id] = {}

            # Convert to serializable format
            offsets_data = {}
            for topic_offset in request.topics:
                offsets_data[topic_offset.topic] = {}
                for partition_offset in topic_offset.partitions:
                    offsets_data[topic_offset.topic][partition_offset.partition] = partition_offset.offset

            kafka_offsets[worker_id][task_id] = {
                "topics": offsets_data,
                "timestamp": request.timestamp
            }

            print(f"[gRPC] Kafka offsets saved for worker {worker_id}, task {task_id}")

            return worker_pb2.SendKafkaOffsetsResponse(
                success=True,
                message="Kafka offsets saved successfully",
                timestamp=time.time()
            )

        except Exception as e:
            print(f"[gRPC] Error saving Kafka offsets: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return worker_pb2.SendKafkaOffsetsResponse(
                success=False,
                message=f"Error: {str(e)}",
                timestamp=time.time()
            )

    def GetKafkaOffsets(self, request, context):
        """Get stored Kafka offsets for a worker and task."""
        try:
            worker_id = request.worker_id
            task_id = request.task_id

            print(f"[gRPC] Kafka offsets requested for worker {worker_id}, task {task_id}")

            if worker_id not in kafka_offsets or task_id not in kafka_offsets[worker_id]:
                # Return empty response if no offsets found
                return worker_pb2.GetKafkaOffsetsResponse(
                    success=True,
                    topics=[],
                    timestamp=time.time()
                )

            # Convert stored data back to proto format
            stored_data = kafka_offsets[worker_id][task_id]
            topics_list = []

            for topic, partitions in stored_data["topics"].items():
                partition_offsets = []
                for partition, offset in partitions.items():
                    partition_offsets.append(
                        worker_pb2.KafkaPartitionOffset(
                            partition=partition,
                            offset=offset
                        )
                    )
                topics_list.append(
                    worker_pb2.KafkaTopicOffsets(
                        topic=topic,
                        partitions=partition_offsets
                    )
                )

            return worker_pb2.GetKafkaOffsetsResponse(
                success=True,
                topics=topics_list,
                timestamp=time.time()
            )

        except Exception as e:
            print(f"[gRPC] Error getting Kafka offsets: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return worker_pb2.GetKafkaOffsetsResponse(
                success=False,
                topics=[],
                timestamp=time.time()
            )

    def Communicate(self, request_iterator, context):
        """Bidirectional streaming for real-time communication.

        worker 通过定期发送 Ping 消息（携带 worker_id）来标识自己的身份；
        master 在收到首条 Ping 后为该 worker 注册消息队列，后续 master 端
        通过 push_master_message / push_task_update 投递的消息会从该队列
        读出并 yield 给 worker。
        """
        worker_id: Optional[str] = None
        msg_queue: Optional[queue.Queue] = None

        # 启动一个后台线程持续读取 worker 发来的消息，
        # 主循环只负责从队列 yield 给 worker，避免阻塞。
        def _consume_requests():
            nonlocal worker_id
            try:
                for worker_msg in request_iterator:
                    # 首次收到 Ping 时注册流
                    if worker_msg.HasField("ping"):
                        if worker_id is None and worker_msg.ping.worker_id:
                            worker_id = worker_msg.ping.worker_id
                            _on_worker_identified()
                        # pong 在主循环外处理不影响（这里仅消费）

                    if worker_msg.HasField("config_ack"):
                        print(f"[gRPC] Received config ack from worker {worker_id}")

                    if worker_msg.HasField("task_status"):
                        ts = worker_msg.task_status
                        print(
                            f"[gRPC] Task status from worker {worker_id}: "
                            f"task={ts.task_id} status={ts.status} msg={ts.message}"
                        )
            except Exception as e:
                print(f"[gRPC] Communicate request reader stopped: {e}")

        def _on_worker_identified():
            nonlocal msg_queue
            msg_queue = self._register_stream(worker_id, context)
            # worker 上线后补发暂存的 PENDING 任务
            try:
                from master.apps.data_collection.dispatcher import (
                    get_default_dispatcher,
                )
                flushed = get_default_dispatcher().flush_pending_tasks(worker_id)
                if flushed:
                    print(f"[gRPC] Flushed {flushed} pending tasks to worker {worker_id}")
            except Exception as e:
                print(f"[gRPC] flush_pending_tasks failed for {worker_id}: {e}")

        reader_thread = threading.Thread(target=_consume_requests, daemon=True)
        reader_thread.start()

        try:
            # 主循环：从队列 yield 消息给 worker
            # 若 worker_id 尚未识别（worker 没发 Ping），则只响应心跳
            while context.is_active():
                if msg_queue is not None:
                    try:
                        master_msg = msg_queue.get(timeout=1)
                        yield master_msg
                    except queue.Empty:
                        continue
                else:
                    # 还未识别身份：等待 reader 线程识别 worker
                    time.sleep(0.2)
        finally:
            if worker_id is not None and msg_queue is not None:
                self._unregister_stream(worker_id, msg_queue)

    # ------------------------------------------------------------------
    # 数据采集模块新增 RPC
    # ------------------------------------------------------------------
    def _verify_dispatch_signature(
        self, worker_id: str, task_id: str, signature: str, timestamp: float
    ) -> bool:
        """校验下发请求的签名。"""
        data_to_verify = {
            "worker_id": worker_id,
            "task_id": task_id,
            "timestamp": timestamp,
        }
        return verify_signature(data_to_verify, signature, SECRET_KEY)

    def DispatchScheduledTask(self, request, context):
        """下发定时数据采集任务。"""
        from master.apps.data_collection.dispatcher import get_default_dispatcher
        from master.apps.data_collection.models import (
            ScheduledTaskConfig as ApiScheduledTaskConfig,
            TaskKind,
        )

        # 签名校验（signature 为空时跳过，方便本地调试）
        if request.signature:
            if not self._verify_dispatch_signature(
                request.worker_id, request.task_id, request.signature, request.timestamp
            ):
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Invalid signature")
                return worker_pb2.DispatchTaskResponse(
                    success=False,
                    message="Invalid signature",
                    worker_id=request.worker_id,
                    task_id=request.task_id,
                    worker_online=self.is_worker_connected(request.worker_id),
                    timestamp=time.time(),
                )

        try:
            adapter_config = json.loads(request.config.adapter_config_json or "{}")
        except json.JSONDecodeError as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"invalid adapter_config_json: {exc}")
            return worker_pb2.DispatchTaskResponse(
                success=False,
                message=f"invalid adapter_config_json: {exc}",
                worker_id=request.worker_id,
                task_id=request.task_id,
                worker_online=self.is_worker_connected(request.worker_id),
                timestamp=time.time(),
            )

        try:
            task_kind = TaskKind(request.config.task_kind) if request.config.task_kind else TaskKind.DATABASE_COLLECTOR
        except ValueError as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"invalid task_kind: {exc}")
            return worker_pb2.DispatchTaskResponse(
                success=False,
                message=f"invalid task_kind: {exc}",
                worker_id=request.worker_id,
                task_id=request.task_id,
                worker_online=self.is_worker_connected(request.worker_id),
                timestamp=time.time(),
            )

        cfg = ApiScheduledTaskConfig(
            cron_expression=request.config.cron_expression,
            adapter_type=request.config.adapter_type,
            adapter_config=adapter_config,
            query=request.config.query or None,
            queries=list(request.config.queries) if request.config.queries else None,
            trade_day_only=request.config.trade_day_only,
            execution_mode=request.config.execution_mode or None,
            task_kind=task_kind,
            extra=dict(request.config.extra),
        )

        dispatcher = get_default_dispatcher()
        result = dispatcher.dispatch_scheduled_task(
            worker_id=request.worker_id,
            config=cfg,
            task_id=request.task_id or None,
        )
        return worker_pb2.DispatchTaskResponse(
            success=result.success,
            message=result.message,
            worker_id=result.worker_id,
            task_id=result.task_id,
            worker_online=result.worker_online,
            timestamp=result.timestamp,
        )

    def DispatchLogTask(self, request, context):
        """下发实时日志采集任务。"""
        from master.apps.data_collection.dispatcher import get_default_dispatcher
        from master.apps.data_collection.models import LogTaskConfig

        if request.signature:
            if not self._verify_dispatch_signature(
                request.worker_id, request.task_id, request.signature, request.timestamp
            ):
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Invalid signature")
                return worker_pb2.DispatchTaskResponse(
                    success=False,
                    message="Invalid signature",
                    worker_id=request.worker_id,
                    task_id=request.task_id,
                    worker_online=self.is_worker_connected(request.worker_id),
                    timestamp=time.time(),
                )

        try:
            source_config = json.loads(request.config.source_config_json or "{}")
        except json.JSONDecodeError as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"invalid source_config_json: {exc}")
            return worker_pb2.DispatchTaskResponse(
                success=False,
                message=f"invalid source_config_json: {exc}",
                worker_id=request.worker_id,
                task_id=request.task_id,
                worker_online=self.is_worker_connected(request.worker_id),
                timestamp=time.time(),
            )

        cfg = LogTaskConfig(
            source_type=request.config.source_type or "file",
            source_config=source_config,
            collect_interval=request.config.collect_interval or 5,
            batch_size=request.config.batch_size or 1000,
            report_interval=request.config.report_interval or 30,
            extra=dict(request.config.extra),
        )

        dispatcher = get_default_dispatcher()
        result = dispatcher.dispatch_log_task(
            worker_id=request.worker_id,
            config=cfg,
            task_id=request.task_id or None,
        )
        return worker_pb2.DispatchTaskResponse(
            success=result.success,
            message=result.message,
            worker_id=result.worker_id,
            task_id=result.task_id,
            worker_online=result.worker_online,
            timestamp=result.timestamp,
        )

    def ControlTask(self, request, context):
        """控制任务：stop / pause / resume。"""
        from master.apps.data_collection.dispatcher import get_default_dispatcher
        from master.apps.data_collection.models import TaskAction

        if request.signature:
            if not self._verify_dispatch_signature(
                request.worker_id, request.task_id, request.signature, request.timestamp
            ):
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Invalid signature")
                return worker_pb2.ControlTaskResponse(
                    success=False,
                    message="Invalid signature",
                    worker_id=request.worker_id,
                    task_id=request.task_id,
                    worker_online=self.is_worker_connected(request.worker_id),
                    timestamp=time.time(),
                )

        try:
            action = TaskAction(request.action)
        except ValueError as exc:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"invalid action: {exc}")
            return worker_pb2.ControlTaskResponse(
                success=False,
                message=f"invalid action: {exc}",
                worker_id=request.worker_id,
                task_id=request.task_id,
                worker_online=self.is_worker_connected(request.worker_id),
                timestamp=time.time(),
            )

        dispatcher = get_default_dispatcher()
        result = dispatcher.control_task(
            worker_id=request.worker_id,
            task_id=request.task_id,
            action=action,
        )
        return worker_pb2.ControlTaskResponse(
            success=result.success,
            message=result.message,
            worker_id=result.worker_id,
            task_id=result.task_id,
            worker_online=result.worker_online,
            timestamp=result.timestamp,
        )

    def ListWorkerTasks(self, request, context):
        """查询指定 worker 上的任务列表（master 端视角）。"""
        from master.apps.data_collection.store import get_default_store

        store = get_default_store()
        records = store.list(request.worker_id)
        tasks = []
        for r in records:
            tasks.append(
                worker_pb2.TaskSummary(
                    task_id=r.task_id,
                    task_type=r.task_kind.value,
                    status=r.status.value,
                    execution_mode=str(r.config.get("execution_mode", "")),
                    config_json=json.dumps(r.config, ensure_ascii=False, default=str),
                    last_updated=r.updated_at,
                )
            )
        return worker_pb2.ListWorkerTasksResponse(
            success=True,
            message=f"{len(tasks)} tasks",
            tasks=tasks,
            timestamp=time.time(),
        )


# Global server instance
_grpc_server = None
_servicer: Optional[WorkerServiceServicer] = None


def _bind_dispatcher(servicer: WorkerServiceServicer) -> None:
    """把 servicer 注入到数据采集模块的 TaskDispatcher。"""
    try:
        from master.apps.data_collection.dispatcher import get_default_dispatcher
        get_default_dispatcher().bind_servicer(servicer)
    except Exception as e:
        print(f"[gRPC] Failed to bind TaskDispatcher: {e}")


def start_grpc_server(port: int = 50051, daemon: bool = True):
    """Start the gRPC server in a background thread."""
    global _grpc_server, _servicer

    if _grpc_server:
        print("gRPC Server already running")
        return

    _servicer = WorkerServiceServicer()
    _bind_dispatcher(_servicer)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    worker_pb2_grpc.add_WorkerServiceServicer_to_server(_servicer, server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()

    _grpc_server = server
    print(f"✅ Master gRPC Server started on port {port} (parallel with HTTP API)")

    if daemon:
        # Run in background thread
        def run_server():
            try:
                server.wait_for_termination()
            except KeyboardInterrupt:
                print("gRPC Server shutdown requested")
                server.stop(0)

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
    else:
        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            print("Shutting down gRPC server...")
            server.stop(0)


def stop_grpc_server():
    """Stop the gRPC server."""
    global _grpc_server, _servicer
    if _grpc_server:
        print("Stopping gRPC server...")
        _grpc_server.stop(0)
        _grpc_server = None
        _servicer = None


if __name__ == "__main__":
    start_grpc_server(daemon=False)
