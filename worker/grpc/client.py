"""
gRPC Client implementation for Worker - Master Communication.
"""

import time
import grpc
import threading
import sys
import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable

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
        central_servers = ["localhost:50051"]
        local_storage_path = "./data"
    settings = Settings()
    
    def generate_signature(data):
        return "dummy-signature"

import worker_pb2
import worker_pb2_grpc

logger = logging.getLogger(__name__)


class CentralGrpcClient:
    """gRPC Client for Worker communication with Master."""
    
    def __init__(self, server_address: Optional[str] = None):
        # Use first central server if not specified
        self.server_address = server_address or settings.central_servers[0]
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
        self._server_health: Dict[str, bool] = {s: True for s in settings.central_servers}
        
        self._connect()
        self._start_heartbeat()
        self.start_communicate_stream()
    
    def _connect(self):
        """Connect to gRPC server with failover support."""
        max_attempts = len(settings.central_servers)
        for attempt in range(max_attempts):
            server_addr = settings.central_servers[self._server_index]
            try:
                self.channel = grpc.insecure_channel(server_addr)
                self.stub = worker_pb2_grpc.WorkerServiceStub(self.channel)
                logger.info(f"Connected to master at {server_addr}")
                self.server_address = server_addr
                return True
            except Exception as e:
                logger.warning(f"Failed to connect to {server_addr}: {e}")
                self._server_health[server_addr] = False
                self._server_index = (self._server_index + 1) % len(settings.central_servers)
        
        logger.error("Failed to connect to any master server")
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
        try:
            request = worker_pb2.HealthCheckRequest(service="worker")
            response = self.stub.HealthCheck(request)
            return response.status == worker_pb2.HealthCheckResponse.SERVING
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
    
    def register(self) -> bool:
        """Register worker with master."""
        try:
            worker_info = worker_pb2.WorkerInfo(
                version=settings.version,
                host=settings.host,
                port=settings.port,
                timestamp=time.time()
            )
            
            data_to_sign = {
                "worker_id": settings.worker_id,
                "info": {
                    "version": settings.version,
                    "host": settings.host,
                    "port": settings.port,
                    "timestamp": worker_info.timestamp
                }
            }
            signature = generate_signature(data_to_sign)
            
            request = worker_pb2.RegisterRequest(
                worker_id=settings.worker_id,
                info=worker_info,
                signature=signature
            )
            
            response = self.stub.RegisterWorker(request)
            
            if response.success:
                self.registered = True
                logger.info(f"Worker {settings.worker_id} registered successfully")
                if response.config:
                    config_dict = dict(response.config)
                    self.save_config(config_dict)
                    logger.info(f"Received config: {config_dict}")
                return True
            else:
                logger.warning(f"Registration failed: {response.message}")
                return False
                
        except Exception as e:
            logger.error(f"Error registering worker: {e}")
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
        while self._heartbeat_running:
            try:
                self.send_heartbeat()
                time.sleep(30)
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                time.sleep(10)
    
    def send_heartbeat(self, status: str = "running") -> bool:
        """Send heartbeat to master."""
        try:
            data_to_sign = {
                "worker_id": settings.worker_id,
                "status": status,
                "timestamp": time.time()
            }
            signature = generate_signature(data_to_sign)
            
            request = worker_pb2.HeartbeatRequest(
                worker_id=settings.worker_id,
                status=status,
                timestamp=time.time(),
                signature=signature
            )
            
            response = self.stub.SendHeartbeat(request)
            return response.success
            
        except Exception as e:
            logger.warning(f"Error sending heartbeat: {e}")
            return False
    
    def send_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """Send logs to master (client streaming)."""
        try:
            def log_generator():
                for log in logs:
                    ts = log.get("timestamp", time.time())
                    if isinstance(ts, str):
                        try:
                            from datetime import datetime
                            ts = datetime.fromisoformat(ts).timestamp()
                        except:
                            ts = time.time()
                    yield worker_pb2.LogEntry(
                        worker_id=settings.worker_id,
                        level=log.get("level", "INFO"),
                        message=log.get("message", ""),
                        source=log.get("source", "worker"),
                        timestamp=ts,
                        metadata=log.get("metadata", {})
                    )
            
            response = self.stub.SendLogs(log_generator())
            logger.debug(f"Sent {response.received_count} logs")
            return response.success
            
        except Exception as e:
            logger.warning(f"Error sending logs: {e}")
            return False
    
    def send_metrics(self, metrics: List[Dict[str, Any]]) -> bool:
        """Send metrics to master (client streaming)."""
        try:
            def metric_generator():
                for metric in metrics:
                    yield worker_pb2.MetricEntry(
                        worker_id=settings.worker_id,
                        name=metric.get("name", ""),
                        value=metric.get("value", 0.0),
                        unit=metric.get("unit", ""),
                        timestamp=metric.get("timestamp", time.time()),
                        labels=metric.get("labels", {})
                    )
            
            response = self.stub.SendMetrics(metric_generator())
            logger.debug(f"Sent {response.received_count} metrics")
            return response.success
            
        except Exception as e:
            logger.warning(f"Error sending metrics: {e}")
            return False
    
    def get_config(self) -> Optional[Dict[str, str]]:
        """Get configuration from master."""
        try:
            request = worker_pb2.GetConfigRequest(worker_id=settings.worker_id)
            response = self.stub.GetConfig(request)
            if response.success:
                config = dict(response.config)
                self.save_config(config)
                return config
            return None
        except Exception as e:
            logger.warning(f"Error getting config, using local cache: {e}")
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
        while self._communicate_running:
            try:
                def message_generator():
                    ping_seq = 1
                    while self._communicate_running:
                        ping = worker_pb2.Ping(sequence=ping_seq, timestamp=time.time())
                        yield worker_pb2.WorkerMessage(ping=ping)
                        ping_seq += 1
                        time.sleep(30)
                
                responses = self.stub.Communicate(message_generator())
                self._communicate_response_iterator = responses
                
                for master_msg in responses:
                    if master_msg.HasField("pong"):
                        logger.debug(f"Received pong: seq={master_msg.pong.sequence}")
                    elif master_msg.HasField("config_update"):
                        config = dict(master_msg.config_update.config)
                        self.save_config(config)
                        if "config_update" in self._message_handlers:
                            asyncio.run_coroutine_threadsafe(
                                self._message_handlers["config_update"]({"config": config}),
                                asyncio.get_event_loop()
                            )
                    elif master_msg.HasField("task_update"):
                        task_update = {
                            "action": master_msg.task_update.action,
                            "task_id": master_msg.task_update.task_id,
                            "task_type": master_msg.task_update.task_type,
                            "config": dict(master_msg.task_update.config)
                        }
                        if "task_update" in self._message_handlers:
                            asyncio.run_coroutine_threadsafe(
                                self._message_handlers["task_update"]({"task": task_update}),
                                asyncio.get_event_loop()
                            )
                    elif master_msg.HasField("trade_day_data"):
                        trade_days = list(master_msg.trade_day_data.trade_days)
                        if "trade_day_data" in self._message_handlers:
                            asyncio.run_coroutine_threadsafe(
                                self._message_handlers["trade_day_data"]({"trade_days": trade_days}),
                                asyncio.get_event_loop()
                            )
            
            except Exception as e:
                logger.error(f"Error in communicate stream: {e}")
                time.sleep(5)
    
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
    
    async def _handle_task_update(self, data):
        """Handle task update messages."""
        if self._task_scheduler:
            task = data.get("task")
            if task:
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
    
    async def _handle_trade_day_data(self, data):
        """Handle trade day data messages."""
        if self._trade_day_cache:
            self._trade_day_cache.update_trade_days_from_data(data)
    
    async def send_websocket_message(self, message: Dict[str, Any]):
        """Compatibility method for sending messages (uses gRPC stream)."""
        # For now, just log the message - in a real implementation we'd use the bidirectional stream
        logger.debug(f"Would send message: {message}")
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
