"""
gRPC Server implementation for Master - Worker Communication.
This runs in parallel with the existing HTTP/REST API.
"""

import asyncio
import json
import queue
import threading
import time
from concurrent import futures
from typing import Any, Dict, List, Optional

import grpc

try:
    from core.security import SECRET_KEY, verify_signature
    from core.settings import settings
except ImportError:
    # Fallback if not running in the full project context
    SECRET_KEY = "test-secret-key"

from . import worker_pb2, worker_pb2_grpc

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
    "metric_batch_size": "500",
}


class WorkerServiceServicer(worker_pb2_grpc.WorkerServiceServicer):
    """Implementation of WorkerService gRPC."""

    def __init__(self):
        # Store bidirectional streams for pushing updates.
        # Key: worker_id; Value: queue.Queue[MasterMessage] (outbound)
        self.active_streams: Dict[str, queue.Queue] = {}
        self._streams_lock = threading.Lock()
        # 后台事件循环引用，供 _handle_task_status 提交回写协程。
        # 在 start_grpc_server 中由独立 daemon 线程 run_forever 驱动。
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def RegisterWorker(self, request, context):
        """Register a worker with the master."""
        # Verify signature
        data_to_verify = {
            "worker_id": request.worker_id,
            "info": {
                "version": request.info.version,
                "host": request.info.host,
                "port": request.info.port,
                "timestamp": request.info.timestamp,
            },
        }

        if not verify_signature(data_to_verify, request.signature, SECRET_KEY):
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details("Invalid signature")
            return worker_pb2.RegisterResponse(
                success=False,
                message="Invalid signature",
                worker_id="",
                config={},
                timestamp=time.time(),
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
                "port": request.info.port,
            },
        }

        print(f"[gRPC] Worker {worker_id} registered successfully")

        return worker_pb2.RegisterResponse(
            success=True,
            message="Worker registered successfully",
            worker_id=worker_id,
            config=worker_config,
            timestamp=time.time(),
        )

    def SendHeartbeat(self, request, context):
        """Process heartbeat from worker."""
        # Verify signature
        data_to_verify = {
            "worker_id": request.worker_id,
            "status": request.status,
            "timestamp": request.timestamp,
        }

        if not verify_signature(data_to_verify, request.signature, SECRET_KEY):
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details("Invalid signature")
            return worker_pb2.HeartbeatResponse(
                success=False, message="Invalid signature", timestamp=time.time()
            )

        worker_id = request.worker_id
        if worker_id not in workers:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Worker not registered")
            return worker_pb2.HeartbeatResponse(
                success=False, message="Worker not registered", timestamp=time.time()
            )

        # Update worker status
        workers[worker_id]["last_heartbeat"] = time.time()
        workers[worker_id]["status"] = request.status

        print(f"[gRPC] Heartbeat from worker {worker_id}")

        return worker_pb2.HeartbeatResponse(
            success=True, message="Heartbeat received", timestamp=time.time()
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
                print(
                    f"[gRPC] Log from {log_entry.worker_id}: [{log_entry.level}] {log_entry.message}"
                )

        except Exception as e:
            print(f"[gRPC] Error receiving logs: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))

        return worker_pb2.SendLogsResponse(
            success=True,
            message=f"Received {received_count} logs",
            received_count=received_count,
            timestamp=time.time(),
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
                print(
                    f"[gRPC] Metric from {metric_entry.worker_id}: {metric_entry.name} = {metric_entry.value} {metric_entry.unit}"
                )

        except Exception as e:
            print(f"[gRPC] Error receiving metrics: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))

        return worker_pb2.SendMetricsResponse(
            success=True,
            message=f"Received {received_count} metrics",
            received_count=received_count,
            timestamp=time.time(),
        )

    def GetConfig(self, request, context):
        """Get configuration for worker."""
        print(f"[gRPC] Config requested by worker {request.worker_id}")

        return worker_pb2.GetConfigResponse(
            success=True, config=worker_config, timestamp=time.time()
        )

    def HealthCheck(self, request, context):
        """Health check."""
        return worker_pb2.HealthCheckResponse(
            status=worker_pb2.HealthCheckResponse.SERVING, timestamp=time.time()
        )

    def SendKafkaOffsets(self, request, context):
        """Receive Kafka offsets from worker and store them."""
        try:
            # Verify signature
            data_to_verify = {
                "worker_id": request.worker_id,
                "task_id": request.task_id,
                "timestamp": request.timestamp,
            }

            if not verify_signature(data_to_verify, request.signature, SECRET_KEY):
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Invalid signature")
                return worker_pb2.SendKafkaOffsetsResponse(
                    success=False, message="Invalid signature", timestamp=time.time()
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
                    offsets_data[topic_offset.topic][partition_offset.partition] = (
                        partition_offset.offset
                    )

            kafka_offsets[worker_id][task_id] = {
                "topics": offsets_data,
                "timestamp": request.timestamp,
            }

            print(f"[gRPC] Kafka offsets saved for worker {worker_id}, task {task_id}")

            return worker_pb2.SendKafkaOffsetsResponse(
                success=True,
                message="Kafka offsets saved successfully",
                timestamp=time.time(),
            )

        except Exception as e:
            print(f"[gRPC] Error saving Kafka offsets: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return worker_pb2.SendKafkaOffsetsResponse(
                success=False, message=f"Error: {str(e)}", timestamp=time.time()
            )

    def GetKafkaOffsets(self, request, context):
        """Get stored Kafka offsets for a worker and task."""
        try:
            worker_id = request.worker_id
            task_id = request.task_id

            print(
                f"[gRPC] Kafka offsets requested for worker {worker_id}, task {task_id}"
            )

            if (
                worker_id not in kafka_offsets
                or task_id not in kafka_offsets[worker_id]
            ):
                # Return empty response if no offsets found
                return worker_pb2.GetKafkaOffsetsResponse(
                    success=True, topics=[], timestamp=time.time()
                )

            # Convert stored data back to proto format
            stored_data = kafka_offsets[worker_id][task_id]
            topics_list = []

            for topic, partitions in stored_data["topics"].items():
                partition_offsets = []
                for partition, offset in partitions.items():
                    partition_offsets.append(
                        worker_pb2.KafkaPartitionOffset(
                            partition=partition, offset=offset
                        )
                    )
                topics_list.append(
                    worker_pb2.KafkaTopicOffsets(
                        topic=topic, partitions=partition_offsets
                    )
                )

            return worker_pb2.GetKafkaOffsetsResponse(
                success=True, topics=topics_list, timestamp=time.time()
            )

        except Exception as e:
            print(f"[gRPC] Error getting Kafka offsets: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return worker_pb2.GetKafkaOffsetsResponse(
                success=False, topics=[], timestamp=time.time()
            )

    def _extract_worker_id(self, context) -> Optional[str]:
        """从 gRPC 调用 metadata 中提取 ``worker_id`` header。

        worker 端在调用 ``Communicate`` 时通过
        ``metadata=[("worker_id", settings.worker_id)]`` 传入；找不到时返回 None，
        由调用方决定回退策略（兼容 worker 端尚未传 metadata 的情况）。
        """
        try:
            metadata = context.invocation_metadata() or []
        except Exception:
            return None
        for key, value in metadata:
            if key.lower() == "worker_id" and value:
                return str(value)
        return None

    def _enqueue_outbound(self, outbound_queue: queue.Queue, master_msg) -> bool:
        """非阻塞入队出站消息；队列满时丢弃最旧并记日志。

        Returns:
            True 表示成功入队。
        """
        while True:
            try:
                outbound_queue.put_nowait(master_msg)
                return True
            except queue.Full:
                try:
                    outbound_queue.get_nowait()
                    print("[gRPC] Outbound queue full, dropped oldest message")
                except queue.Empty:
                    # 极端并发：刚被其他线程取走，重试入队
                    continue

    def push_task_update(self, worker_id: str, task_update_dict: dict) -> bool:
        """向指定 worker 的活跃流推送一条 ``TaskUpdate`` 消息。

        Args:
            worker_id: 目标 worker 标识。
            task_update_dict: 任务更新内容，支持字段：
                - task_id (str)
                - action (str): "create" / "stop" / "pause" / "resume"
                - task_type (str)
                - config (dict | str): 若为 dict/list 会自动 JSON 序列化为字符串
                - timestamp (float): 可选，默认当前时间

        Returns:
            True 表示成功入队；False 表示该 worker 当前无活跃流。
        """
        with self._streams_lock:
            outbound_queue = self.active_streams.get(worker_id)
        if outbound_queue is None:
            print(
                f"[gRPC] push_task_update: no active stream for worker {worker_id}"
            )
            return False

        # 构造 config JSON 字符串（proto 中 config 字段为 string 类型）
        config_value = task_update_dict.get("config", "")
        if isinstance(config_value, (dict, list)):
            try:
                config_str = json.dumps(config_value, ensure_ascii=False)
            except (TypeError, ValueError):
                config_str = ""
        elif isinstance(config_value, str):
            config_str = config_value
        elif config_value is None:
            config_str = ""
        else:
            try:
                config_str = json.dumps(config_value, ensure_ascii=False)
            except (TypeError, ValueError):
                config_str = str(config_value)

        timestamp = task_update_dict.get("timestamp")
        if timestamp is None:
            timestamp = time.time()

        task_update = worker_pb2.TaskUpdate(
            task_id=str(task_update_dict.get("task_id", "")),
            action=str(task_update_dict.get("action", "")),
            task_type=str(task_update_dict.get("task_type", "")),
            config=config_str,
            timestamp=float(timestamp),
            worker_id=worker_id,
        )
        master_msg = worker_pb2.MasterMessage(task_update=task_update)
        return self._enqueue_outbound(outbound_queue, master_msg)

    def _handle_task_status(self, task_status_msg) -> None:
        """处理 worker 上报的 ``TaskStatus``，回写 master 端 ``CollectorTask``。

        在 gRPC 流线程中被 ``Communicate`` 主循环调用，仅做轻量的字段提取与
        协程提交；真正的数据库回写在后台事件循环中执行，避免阻塞 gRPC 流。
        所有异常仅记日志，不向上抛出，避免击穿 gRPC 双向流。

        Args:
            task_status_msg: ``worker_pb2.TaskStatus`` proto 消息对象。
        """
        try:
            task_id_str = task_status_msg.task_id or ""
            if not task_id_str:
                # 备选查找键：extra 中的 job_id
                extra = (
                    dict(task_status_msg.extra) if task_status_msg.extra else {}
                )
                task_id_str = extra.get("job_id", "") or ""

            if not task_id_str:
                print(
                    "[gRPC][WARN] _handle_task_status: empty task_id, "
                    f"skip writeback. status={task_status_msg.status}"
                )
                return

            try:
                int(task_id_str)
            except (TypeError, ValueError):
                print(
                    "[gRPC][WARN] _handle_task_status: invalid task_id="
                    f"{task_id_str!r}, skip writeback"
                )
                return

            loop = self._loop
            if loop is None:
                print(
                    "[gRPC][WARN] _handle_task_status: no event loop available, "
                    "skip writeback"
                )
                return

            asyncio.run_coroutine_threadsafe(
                self._writeback_collector_task(task_status_msg), loop
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[gRPC][ERROR] _handle_task_status: {exc}")

    async def _writeback_collector_task(self, task_status_msg) -> None:
        """根据 worker 上报的 ``TaskStatus`` 回写 ``CollectorTask`` 表。

        在后台事件循环中执行（由 ``_handle_task_status`` 通过
        ``asyncio.run_coroutine_threadsafe`` 提交）。所有异常仅记日志，
        不向上抛出，避免击穿 gRPC 双向流。

        回写规则（按 ``task_status_msg.status`` 字符串分发）：
            - ``success``：``exec_status``/``last_run_status`` 置 success，
              写 ``last_run_duration_ms``/``last_run_time``，``total_run_count +1``；
              不修改 ``status`` 字段（执行成功不改变任务整体状态）。
            - ``failed``：``exec_status``/``last_run_status`` 置 failed，
              ``total_run_count +1``、``total_failed_count +1``，
              ``status`` 置 ``TaskStatus.error``（5）。
            - ``running``：``exec_status`` 置 running，写 ``last_run_time``；
              不修改 ``total_*`` 与 ``last_run_status``。
            - 其他：仅记 info 日志，不修改任何字段。
        """
        try:
            from datetime import datetime

            from sqlalchemy import select

            from apps.collector.models import (
                CollectorTask,
                ExecStatus,
                TaskStatus as CollectorTaskStatus,
            )
            from core.globals import site

            task_id_str = task_status_msg.task_id or ""
            try:
                task_pk = int(task_id_str)
            except (TypeError, ValueError):
                print(
                    "[gRPC][WARN] _writeback_collector_task: invalid task_id="
                    f"{task_id_str!r}"
                )
                return

            status_str = (task_status_msg.status or "").strip().lower()
            timestamp = (
                float(task_status_msg.timestamp)
                if task_status_msg.timestamp
                else 0.0
            )
            duration_ms = (
                int(task_status_msg.duration_ms)
                if task_status_msg.duration_ms
                else 0
            )
            extra = (
                dict(task_status_msg.extra) if task_status_msg.extra else {}
            )

            # site.db 是 AsyncDatabase（sqlalchemy_database 0.1.2）。
            # 该版本未注入 ``async_session`` 代理属性，但 ``session_maker``
            # 同样返回 ``AsyncSession`` 且支持 ``async with``；
            # 这里优先尝试 ``async_session``（兼容未来版本/其他 db 后端），
            # 不可用时回退到 ``session_maker``。
            async_session_factory = getattr(site.db, "async_session", None) or getattr(
                site.db, "session_maker", None
            )
            if async_session_factory is None:
                print(
                    "[gRPC][ERROR] _writeback_collector_task: site.db has "
                    "neither async_session nor session_maker"
                )
                return

            async with async_session_factory() as sess:
                stmt = select(CollectorTask).where(CollectorTask.id == task_pk)
                task = (await sess.execute(stmt)).scalars().first()
                if task is None:
                    print(
                        "[gRPC][WARN] _writeback_collector_task: "
                        f"CollectorTask id={task_pk} not found"
                    )
                    return

                # last_run_time 在 CollectorTask 模型中是 str 类型，务必转字符串
                last_run_time_str = (
                    datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    if timestamp
                    else ""
                )

                if status_str == "success":
                    task.exec_status = ExecStatus.success
                    task.last_run_status = ExecStatus.success
                    task.last_run_duration_ms = duration_ms
                    if last_run_time_str:
                        task.last_run_time = last_run_time_str
                    task.total_run_count = (task.total_run_count or 0) + 1
                    # success 不改 CollectorTask.status 字段
                elif status_str == "failed":
                    task.exec_status = ExecStatus.failed
                    task.last_run_status = ExecStatus.failed
                    task.last_run_duration_ms = duration_ms
                    if last_run_time_str:
                        task.last_run_time = last_run_time_str
                    task.total_run_count = (task.total_run_count or 0) + 1
                    task.total_failed_count = (task.total_failed_count or 0) + 1
                    task.status = CollectorTaskStatus.error
                elif status_str == "running":
                    task.exec_status = ExecStatus.running
                    if last_run_time_str:
                        task.last_run_time = last_run_time_str
                    # running 不修改 total_* 与 last_run_status
                else:
                    # paused / stopped / 未知状态：仅记日志，不修改字段
                    print(
                        "[gRPC][INFO] _writeback_collector_task: "
                        f"non-mutating status={status_str!r} for task id={task_pk}"
                    )
                    return

                if "transformed_rows" in extra:
                    # CollectorTask 模型无对应字段，spec 允许忽略，仅记 debug
                    print(
                        "[gRPC][DEBUG] _writeback_collector_task: task "
                        f"id={task_pk} transformed_rows="
                        f"{extra.get('transformed_rows')!r} (ignored, "
                        "CollectorTask has no such field)"
                    )

                await sess.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"[gRPC][ERROR] _writeback_collector_task: {exc}")

    def Communicate(self, request_iterator, context):
        """Bidirectional streaming for real-time communication.

        改造为按 ``worker_id`` 索引活跃流，使用双队列方案：
        - 入站：daemon 线程消费 ``request_iterator`` -> ``inbound_queue``
        - 出站：主循环从 ``outbound_queue`` 取消息 yield 给 worker
        外部调用 ``push_task_update`` 时入队到 ``outbound_queue``。
        """
        worker_id = self._extract_worker_id(context)
        if not worker_id:
            worker_id = "stream-worker-" + str(int(time.time()))
            print(
                "[gRPC] WARNING: Communicate missing 'worker_id' metadata, "
                f"fallback to placeholder id {worker_id}"
            )

        outbound_queue: queue.Queue = queue.Queue(maxsize=100)
        inbound_queue: queue.Queue = queue.Queue()

        with self._streams_lock:
            self.active_streams[worker_id] = outbound_queue

        inbound_error: list = []

        def consume_inbound():
            try:
                for worker_msg in request_iterator:
                    inbound_queue.put(worker_msg)
            except Exception as exc:  # noqa: BLE001
                inbound_error.append(exc)
            finally:
                # 哨兵：通知主循环入站流已结束
                inbound_queue.put(None)

        inbound_thread = threading.Thread(target=consume_inbound, daemon=True)
        inbound_thread.start()

        print(
            f"[gRPC] Bidirectional stream established for worker {worker_id}"
        )

        try:
            while True:
                # 1. 优先 yield 待发的出站消息
                try:
                    master_msg = outbound_queue.get_nowait()
                    yield master_msg
                    continue
                except queue.Empty:
                    pass

                # 2. 处理入站消息（非阻塞）
                try:
                    item = inbound_queue.get_nowait()
                except queue.Empty:
                    if not inbound_thread.is_alive():
                        # 入站流已结束且无积压消息：排干出站后退出
                        while True:
                            try:
                                master_msg = outbound_queue.get_nowait()
                            except queue.Empty:
                                break
                            yield master_msg
                        if inbound_error:
                            print(
                                f"[gRPC] Inbound stream error for worker "
                                f"{worker_id}: {inbound_error[0]}"
                            )
                        break
                    time.sleep(0.05)
                    continue

                if item is None:
                    # 入站流显式结束：排干出站队列后退出
                    while True:
                        try:
                            master_msg = outbound_queue.get_nowait()
                        except queue.Empty:
                            break
                        yield master_msg
                    if inbound_error:
                        print(
                            f"[gRPC] Inbound stream error for worker "
                            f"{worker_id}: {inbound_error[0]}"
                        )
                    break

                worker_msg = item
                if worker_msg.HasField("ping"):
                    pong = worker_pb2.Pong(
                        sequence=worker_msg.ping.sequence,
                        timestamp=time.time(),
                    )
                    self._enqueue_outbound(
                        outbound_queue, worker_pb2.MasterMessage(pong=pong)
                    )
                elif worker_msg.HasField("config_ack"):
                    print(
                        f"[gRPC] Received config ack from worker {worker_id}"
                    )
                elif worker_msg.HasField("task_status"):
                    self._handle_task_status(worker_msg.task_status)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[gRPC] Error in bidirectional stream for worker {worker_id}: {exc}"
            )
        finally:
            with self._streams_lock:
                if self.active_streams.get(worker_id) is outbound_queue:
                    del self.active_streams[worker_id]
            print(f"[gRPC] Bidirectional stream closed for worker {worker_id}")


# Global server instance
_grpc_server = None

# Global servicer singleton (set in start_grpc_server, read by HTTP layer)
_servicer: Optional[WorkerServiceServicer] = None


def start_grpc_server(port: int = 50051, daemon: bool = True):
    """Start the gRPC server in a background thread."""
    global _grpc_server, _servicer

    if _grpc_server:
        print("gRPC Server already running")
        return

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    _servicer = WorkerServiceServicer()

    # 启动一个独立的后台事件循环，供 servicer 提交回写协程。
    # gRPC servicer 运行在 grpc thread pool 中，主线程/主事件循环可能
    # 不可用（master 在 lifespan 子线程中启动 gRPC），因此为 servicer
    # 维护一个独立 loop，所有 run_coroutine_threadsafe 都提交到此 loop。
    try:
        bg_loop = asyncio.new_event_loop()

        def _run_bg_loop():
            asyncio.set_event_loop(bg_loop)
            bg_loop.run_forever()

        threading.Thread(target=_run_bg_loop, daemon=True).start()
        _servicer._loop = bg_loop
    except Exception as exc:  # noqa: BLE001
        print(
            "[gRPC][ERROR] start_grpc_server: failed to start background "
            f"event loop for writeback: {exc}"
        )

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


def get_servicer() -> Optional[WorkerServiceServicer]:
    """返回全局 WorkerServiceServicer 单例。

    master HTTP 路由层可通过此函数拿到 servicer 实例后调用
    ``push_task_update`` 向指定 worker 下发任务。
    若 gRPC 服务尚未启动，返回 None。
    """
    return _servicer


def list_workers() -> List[Dict[str, Any]]:
    """返回当前已注册 worker 的快照列表。

    每项含 ``worker_id`` / ``host`` / ``port`` / ``status`` /
    ``last_heartbeat`` / ``version``（version/host/port 取自 info）。
    """
    # 浅拷贝 items，避免并发注册/心跳写入时迭代出错
    items = list(workers.items())
    result: List[Dict[str, Any]] = []
    for worker_id, w in items:
        w = w or {}
        info = w.get("info") or {}
        result.append(
            {
                "worker_id": w.get("worker_id", worker_id),
                "host": info.get("host", ""),
                "port": info.get("port", 0),
                "status": w.get("status", ""),
                "last_heartbeat": w.get("last_heartbeat", 0.0),
                "version": info.get("version", ""),
            }
        )
    return result


if __name__ == "__main__":
    start_grpc_server(daemon=False)
