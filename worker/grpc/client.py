"""
gRPC Client implementation for Worker - Master Communication.
"""

import time
import grpc
import threading
import sys
import os
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from urllib.parse import urlparse

# Add the current directory to path for gRPC modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from worker.core.settings import settings
    from worker.core.auth import generate_signature
except ImportError:
    # Fallback if not running in the full project context
    class Settings:
        worker_id = "test-worker-001"
        version = "1.0.0"
        host = "localhost"
        port = 5001
        grpc_enabled = True
        grpc_server_address = "localhost:50051"
        grpc_server_addresses = ["localhost:50051"]
        local_storage_path = "./data"
    settings = Settings()

    def generate_signature(data):
        return "dummy-signature"

import worker_pb2
import worker_pb2_grpc

logger = logging.getLogger(__name__)


def _normalize_grpc_address(raw: str) -> str:
    """把 ``http://host:port/path`` 或 ``host:port`` 规范化为 ``host:port``。

    gRPC 的 insecure_channel / secure_channel 只接受 ``host:port`` 形式，
    不能带 ``http://``、``https://`` 以及路径。
    """
    if raw is None:
        return ""
    s = raw.strip()
    if not s:
        return ""
    # 如果没有 scheme，补一个以便 urlparse 正确工作
    if "://" not in s:
        s = "grpc://" + s
    parsed = urlparse(s)
    host = parsed.hostname or "localhost"
    port = parsed.port
    if port is None:
        # 默认 gRPC 端口
        port = 50051
    return f"{host}:{port}"


def _collect_grpc_addresses() -> List[str]:
    """从 settings 中收集所有候选 gRPC 地址并规范化。"""
    candidates: List[str] = []
    # 1. 优先使用显式列表配置
    addresses = getattr(settings, "grpc_server_addresses", None) or []
    if isinstance(addresses, (list, tuple)):
        candidates.extend(addresses)
    # 2. 其次使用单个地址配置（逗号分隔也可视为多个）
    single = getattr(settings, "grpc_server_address", None) or ""
    if isinstance(single, str) and single:
        candidates.extend(single.split(","))
    # 3. 最后回退到 central_servers（兼容历史配置）
    fallback = getattr(settings, "central_servers", None) or []
    if isinstance(fallback, (list, tuple)):
        candidates.extend(fallback)

    normalized: List[str] = []
    seen: set = set()
    for c in candidates:
        addr = _normalize_grpc_address(c)
        if addr and addr not in seen:
            seen.add(addr)
            normalized.append(addr)
    if not normalized:
        normalized = ["localhost:50051"]
    return normalized


class CentralGrpcClient:
    """gRPC Client for Worker communication with Master."""
    
    def __init__(self, server_address: Optional[str] = None):
        # 收集候选地址：显式传入 > settings.grpc_server_address(es) > settings.central_servers
        if server_address:
            self._candidate_addresses: List[str] = [_normalize_grpc_address(server_address)]
        else:
            self._candidate_addresses = _collect_grpc_addresses()

        self.server_address: str = self._candidate_addresses[0]
        self.channel = None
        self.stub = None
        self.registered = False

        # Message handlers for bidirectional stream
        self._message_handlers: Dict[str, Callable] = {}

        # Task scheduler and trade day cache references
        self._task_scheduler = None
        self._trade_day_cache = None

        # Local config storage
        self._local_config_path = os.path.join(settings.local_storage_path, "worker_config.json")

        # Streaming state
        self._communicate_thread = None
        self._communicate_running = False
        self._communicate_response_iterator = None
        self._communicate_lock = threading.Lock()

        # Heartbeat thread
        self._heartbeat_thread = None
        self._heartbeat_running = False

        # Server health and failover
        self._server_index = 0
        self._server_health: Dict[str, bool] = {s: True for s in self._candidate_addresses}

        # 延迟初始化：仅在显式调用 register / send_* / health_check 时建立连接
        # 避免 master 不可用时产生大量错误日志噪音。
        self._connected = False

    def _ensure_connected(self) -> bool:
        """惰性建立连接，失败时进行故障转移并返回是否成功。

        连接成功时启动心跳与双向流线程。
        """
        if self._connected and self.channel is not None:
            return True
        return self._connect()

    def _connect(self) -> bool:
        """Connect to gRPC server with failover support."""
        max_attempts = len(self._candidate_addresses)
        last_error: Optional[Exception] = None
        for attempt in range(max_attempts):
            server_addr = self._candidate_addresses[
                (self._server_index + attempt) % len(self._candidate_addresses)
            ]
            try:
                # 关闭旧 channel
                if self.channel is not None:
                    try:
                        self.channel.close()
                    except Exception:
                        pass
                self.channel = grpc.insecure_channel(
                    server_addr,
                    options=[
                        ("grpc.keepalive_time_ms", 30_000),
                        ("grpc.keepalive_timeout_ms", 10_000),
                        ("grpc.keepalive_permit_without_calls", 1),
                    ],
                )
                self.stub = worker_pb2_grpc.WorkerServiceStub(self.channel)
                self.server_address = server_addr
                self._server_index = (self._server_index + attempt) % len(self._candidate_addresses)
                self._connected = True
                logger.info("Connected to master at %s (attempt %d/%d)", server_addr, attempt + 1, max_attempts)
                # 连接成功后再启动心跳与流线程，避免初始化阶段产生噪音
                if not self._heartbeat_running:
                    self._start_heartbeat()
                if not self._communicate_running:
                    self.start_communicate_stream()
                return True
            except Exception as exc:
                last_error = exc
                logger.warning("Failed to connect to %s: %s", server_addr, exc)
                self._server_health[server_addr] = False
        logger.error("Failed to connect to any master server (last error: %s)", last_error)
        self._connected = False
        return False
    
    def close(self):
        """Close the connection."""
        self._stop_communicate_stream()
        self._stop_heartbeat()
        if self.channel:
            self.channel.close()
            logger.info("Connection closed")
    
    def health_check(self) -> bool:
        """Check if master is healthy."""
        if not self._ensure_connected():
            return False
        try:
            request = worker_pb2.HealthCheckRequest(service="worker")
            response = self.stub.HealthCheck(request)
            return response.status == worker_pb2.HealthCheckResponse.SERVING
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            return False

    def register(self) -> bool:
        """Register worker with master."""
        if not self._ensure_connected():
            logger.warning("Cannot register worker: master unreachable at %s", self.server_address)
            return False
        try:
            worker_info = worker_pb2.WorkerInfo(
                version=settings.version,
                host=settings.host,
                port=settings.port,
                timestamp=time.time(),
            )

            data_to_sign = {
                "worker_id": settings.worker_id,
                "info": {
                    "version": settings.version,
                    "host": settings.host,
                    "port": settings.port,
                    "timestamp": worker_info.timestamp,
                },
            }
            signature = generate_signature(data_to_sign)

            request = worker_pb2.RegisterRequest(
                worker_id=settings.worker_id,
                info=worker_info,
                signature=signature,
            )

            response = self.stub.RegisterWorker(request)

            if response.success:
                self.registered = True
                logger.info("Worker %s registered successfully", settings.worker_id)
                if response.config:
                    config_dict = dict(response.config)
                    self.save_config(config_dict)
                    logger.info("Received config: %s", config_dict)
                return True
            else:
                logger.warning("Registration failed: %s", response.message)
                return False

        except Exception as e:
            logger.error("Error registering worker: %s", e)
            return False

    def _start_heartbeat(self):
        """Start heartbeat thread."""
        if self._heartbeat_running:
            return
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        logger.info("Heartbeat thread started")

    def _stop_heartbeat(self):
        """Stop heartbeat thread."""
        self._heartbeat_running = False
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2)

    def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        # 为避免 master 还没连接时打日志噪音：未连接时使用较短的退避
        backoff = 10
        while self._heartbeat_running:
            try:
                if not self._connected:
                    if not self._ensure_connected():
                        # master 尚未可用，指数退避
                        backoff = min(backoff * 2, 120)
                        time.sleep(backoff)
                        continue
                self.send_heartbeat()
                backoff = 30
                time.sleep(backoff)
            except Exception as e:
                logger.error("Error in heartbeat loop: %s", e)
                time.sleep(10)

    def send_heartbeat(self, status: str = "running") -> bool:
        """Send heartbeat to master."""
        if not self._connected:
            return False
        try:
            data_to_sign = {
                "worker_id": settings.worker_id,
                "status": status,
                "timestamp": time.time(),
            }
            signature = generate_signature(data_to_sign)

            request = worker_pb2.HeartbeatRequest(
                worker_id=settings.worker_id,
                status=status,
                timestamp=time.time(),
                signature=signature,
            )

            response = self.stub.SendHeartbeat(request)
            return response.success

        except Exception as e:
            logger.warning("Error sending heartbeat: %s", e)
            return False

    def send_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """Send logs to master (client streaming)."""
        if not self._ensure_connected():
            return False
        try:
            def log_generator():
                for log in logs:
                    ts = log.get("timestamp", time.time())
                    if isinstance(ts, str):
                        try:
                            from datetime import datetime

                            ts = datetime.fromisoformat(ts).timestamp()
                        except Exception:
                            ts = time.time()
                    yield worker_pb2.LogEntry(
                        worker_id=settings.worker_id,
                        level=log.get("level", "INFO"),
                        message=log.get("message", ""),
                        source=log.get("source", "worker"),
                        timestamp=ts,
                        metadata=log.get("metadata", {}),
                    )

            response = self.stub.SendLogs(log_generator())
            logger.debug("Sent %d logs", response.received_count)
            return response.success

        except Exception as e:
            logger.warning("Error sending logs: %s", e)
            return False

    def send_metrics(self, metrics: List[Dict[str, Any]]) -> bool:
        """Send metrics to master (client streaming)."""
        if not self._ensure_connected():
            return False
        try:
            def metric_generator():
                for metric in metrics:
                    yield worker_pb2.MetricEntry(
                        worker_id=settings.worker_id,
                        name=metric.get("name", ""),
                        value=float(metric.get("value", 0.0)),
                        unit=metric.get("unit", ""),
                        timestamp=metric.get("timestamp", time.time()),
                        labels=metric.get("labels", {}),
                    )

            response = self.stub.SendMetrics(metric_generator())
            logger.debug("Sent %d metrics", response.received_count)
            return response.success

        except Exception as e:
            logger.warning("Error sending metrics: %s", e)
            return False

    def get_config(self) -> Optional[Dict[str, str]]:
        """Get configuration from master."""
        if not self._ensure_connected():
            return self.load_config()
        try:
            request = worker_pb2.GetConfigRequest(worker_id=settings.worker_id)
            response = self.stub.GetConfig(request)
            if response.success:
                config = dict(response.config)
                self.save_config(config)
                return config
            return None
        except Exception as e:
            logger.warning("Error getting config, using local cache: %s", e)
            return self.load_config()
    
    def save_config(self, config: Dict[str, Any]):
        """Save config to local storage."""
        try:
            os.makedirs(settings.local_storage_path, exist_ok=True)
            with open(self._local_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f)
            logger.info("Config saved to local storage")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def load_config(self) -> Optional[Dict[str, Any]]:
        """Load config from local storage."""
        try:
            if os.path.exists(self._local_config_path):
                with open(self._local_config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                logger.info("Loaded config from local storage")
                return config
            else:
                logger.warning("No local config found")
                return None
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return None
    
    def send_kafka_offsets(self, task_id: str, offsets: Dict[str, Dict[int, int]]) -> bool:
        """Send Kafka offsets to master."""
        try:
            topics_list = []
            for topic, partitions in offsets.items():
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
            
            timestamp = time.time()
            data_to_sign = {
                "worker_id": settings.worker_id,
                "task_id": task_id,
                "timestamp": timestamp
            }
            signature = generate_signature(data_to_sign)
            
            request = worker_pb2.SendKafkaOffsetsRequest(
                worker_id=settings.worker_id,
                task_id=task_id,
                topics=topics_list,
                timestamp=timestamp,
                signature=signature
            )
            
            response = self.stub.SendKafkaOffsets(request)
            return response.success
        except Exception as e:
            logger.warning(f"Error sending Kafka offsets: {e}")
            return False
    
    def get_kafka_offsets(self, task_id: str) -> Optional[Dict[str, Dict[int, int]]]:
        """Get Kafka offsets from master for a task."""
        try:
            request = worker_pb2.GetKafkaOffsetsRequest(
                worker_id=settings.worker_id,
                task_id=task_id
            )
            
            response = self.stub.GetKafkaOffsets(request)
            
            if response.success:
                offsets = {}
                for topic_offset in response.topics:
                    offsets[topic_offset.topic] = {}
                    for partition_offset in topic_offset.partitions:
                        offsets[topic_offset.topic][partition_offset.partition] = partition_offset.offset
                return offsets
            return None
        except Exception as e:
            logger.warning(f"Error getting Kafka offsets: {e}")
            return None
    
    def _start_communicate_stream(self):
        """Internal method to run the bidirectional stream."""
        backoff = 1
        while self._communicate_running:
            # 没有连接就继续退避等待，避免 master 没启动时打大量错误日志
            if not self._connected or self.stub is None:
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            try:
                def message_generator():
                    ping_seq = 1
                    while self._communicate_running and self._connected:
                        ping = worker_pb2.Ping(sequence=ping_seq, timestamp=time.time())
                        yield worker_pb2.WorkerMessage(ping=ping)
                        ping_seq += 1
                        time.sleep(30)

                responses = self.stub.Communicate(message_generator())
                self._communicate_response_iterator = responses
                backoff = 1

                for master_msg in responses:
                    if not self._communicate_running:
                        break
                    if master_msg.HasField("pong"):
                        logger.debug("Received pong: seq=%s", master_msg.pong.sequence)
                    elif master_msg.HasField("config_update"):
                        config = dict(master_msg.config_update.config)
                        self.save_config(config)
                        handler = self._message_handlers.get("config_update")
                        if handler is not None:
                            try:
                                handler({"config": config})
                            except Exception as exc:
                                logger.error("config_update handler failed: %s", exc)
                    elif master_msg.HasField("task_update"):
                        task_update = {
                            "action": master_msg.task_update.action,
                            "task_id": master_msg.task_update.task_id,
                            "task_type": master_msg.task_update.task_type,
                            "config": dict(master_msg.task_update.config),
                        }
                        handler = self._message_handlers.get("task_update")
                        if handler is not None:
                            try:
                                handler({"task": task_update})
                            except Exception as exc:
                                logger.error("task_update handler failed: %s", exc)
                    elif master_msg.HasField("trade_day_data"):
                        trade_days = list(master_msg.trade_day_data.trade_days)
                        handler = self._message_handlers.get("trade_day_data")
                        if handler is not None:
                            try:
                                handler({"trade_days": trade_days})
                            except Exception as exc:
                                logger.error("trade_day_data handler failed: %s", exc)

            except Exception as e:
                # master 断线时只打一次警告，退避后重试
                logger.warning("Communicate stream lost, reconnecting in %ds: %s", backoff, e)
                self._connected = False
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
    
    def start_communicate_stream(self):
        """Start bidirectional streaming communication."""
        if not self._communicate_running:
            self._communicate_running = True
            self._communicate_thread = threading.Thread(
                target=self._start_communicate_stream,
                daemon=True
            )
            self._communicate_thread.start()
            logger.info("Started bidirectional communication stream")
    
    def _stop_communicate_stream(self):
        """Stop bidirectional streaming."""
        self._communicate_running = False
        if self._communicate_thread and self._communicate_thread.is_alive():
            self._communicate_thread.join(timeout=2)
    
    def register_message_handler(self, message_type: str, handler):
        """Register a message handler for the bidirectional stream."""
        self._message_handlers[message_type] = handler
        logger.info(f"Registered message handler for type: {message_type}")
    
    def unregister_message_handler(self, message_type: str):
        """Unregister a message handler."""
        if message_type in self._message_handlers:
            del self._message_handlers[message_type]
    
    def register_task_scheduler(self, scheduler):
        """Register task scheduler to receive task updates."""
        self._task_scheduler = scheduler
        self.register_message_handler("task_update", self._handle_task_update)
        logger.info("TaskScheduler registered")
    
    def set_trade_day_cache(self, cache):
        """Set trade day cache reference."""
        self._trade_day_cache = cache
        self.register_message_handler("trade_day_data", self._handle_trade_day_data)
        logger.info("TradeDayCache set")
    
    def _handle_task_update(self, data):
        """Handle task update messages."""
        if self._task_scheduler is None:
            return
        task = data.get("task")
        if not task:
            return
        action = task.get("action")
        config = task.get("config", {})
        if action == "task_create":
            self._task_scheduler.create_task(task.get("task_type"), config)
        elif action == "task_stop":
            self._task_scheduler.stop_task(task.get("task_id"))
        elif action == "task_pause":
            self._task_scheduler.pause_task(task.get("task_id"))
        elif action == "task_resume":
            self._task_scheduler.resume_task(task.get("task_id"))

    def _handle_trade_day_data(self, data):
        """Handle trade day data messages."""
        if self._trade_day_cache:
            self._trade_day_cache.update_trade_days_from_data(data)

    def send_websocket_message(self, message: Dict[str, Any]) -> bool:
        """Compatibility method for sending messages (uses gRPC stream)."""
        # For now, just log the message - in a real implementation we'd use the bidirectional stream
        logger.debug("Would send message: %s", message)
        return True


def run_demo():
    """Run a demo of the gRPC client."""
    print("=" * 70)
    print("gRPC Worker Client Demo")
    print("=" * 70)
    
    # Create client
    print("\n[1] Creating gRPC client...")
    client = CentralGrpcClient("localhost:50051")
    
    # Health check
    print("\n[2] Health check...")
    healthy = client.health_check()
    print(f"    Master health: {'✓ Healthy' if healthy else '✗ Unhealthy'}")
    
    if not healthy:
        print("\nMaster is not available. Please start the gRPC server first.")
        return
    
    # Register
    print("\n[3] Registering worker...")
    registered = client.register()
    
    if registered:
        # Heartbeat
        print("\n[4] Sending heartbeat...")
        heartbeat_ok = client.send_heartbeat()
        print(f"    Heartbeat: {'✓ OK' if heartbeat_ok else '✗ FAILED'}")
        
        # Send logs
        print("\n[5] Sending test logs...")
        test_logs = [
            {"level": "INFO", "message": "Worker started (gRPC)", "source": "demo"},
            {"level": "WARN", "message": "High memory usage", "source": "monitor"},
            {"level": "INFO", "message": "Processing completed", "source": "worker"}
        ]
        logs_ok = client.send_logs(test_logs)
        print(f"    Logs: {'✓ OK' if logs_ok else '✗ FAILED'}")
        
        # Get config
        print("\n[6] Getting config...")
        config = client.get_config()
        if config:
            print(f"    ✓ Config: {config}")
    
    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)
    
    client.close()


if __name__ == "__main__":
    run_demo()
