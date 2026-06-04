"""
gRPC Client implementation for Worker - Master Communication.
This can work in parallel with the existing HTTP/REST client.
"""

import time
import grpc
import threading
import sys
import os
from typing import Dict, Any, List, Optional

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
    settings = Settings()
    
    def generate_signature(data):
        return "dummy-signature"

import worker_pb2
import worker_pb2_grpc


class CentralGrpcClient:
    """gRPC Client for Worker communication with Master."""
    
    def __init__(self, server_address: str = "localhost:50051"):
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self.registered = False
        
        # Streaming state
        self._communicate_thread = None
        self._communicate_running = False
        
        self._connect()
    
    def _connect(self):
        """Connect to gRPC server."""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = worker_pb2_grpc.WorkerServiceStub(self.channel)
            print(f"[gRPC] Connected to master at {self.server_address}")
        except Exception as e:
            print(f"[gRPC] Failed to connect to master: {e}")
    
    def close(self):
        """Close the connection."""
        self._stop_communicate_stream()
        if self.channel:
            self.channel.close()
            print("[gRPC] Connection closed")
    
    def health_check(self) -> bool:
        """Check if master is healthy."""
        try:
            request = worker_pb2.HealthCheckRequest(service="worker")
            response = self.stub.HealthCheck(request)
            return response.status == worker_pb2.HealthCheckResponse.SERVING
        except Exception as e:
            print(f"[gRPC] Health check failed: {e}")
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
            
            # Generate signature
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
                print(f"[gRPC] ✓ Worker {settings.worker_id} registered successfully")
                if response.config:
                    config_dict = dict(response.config)
                    print(f"[gRPC]   Received config: {config_dict}")
                    # 应用配置
                    try:
                        settings.update_from_dict(config_dict)
                        print(f"[gRPC]   Applied config")
                    except Exception as e:
                        print(f"[gRPC]   Error applying config: {e}")
                return True
            else:
                print(f"[gRPC] Registration failed: {response.message}")
                return False
                
        except Exception as e:
            print(f"[gRPC] Error registering worker: {e}")
            return False
    
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
            print(f"[gRPC] Error sending heartbeat: {e}")
            return False
    
    def send_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """Send logs to master (client streaming)."""
        try:
            def log_generator():
                for log in logs:
                    yield worker_pb2.LogEntry(
                        worker_id=settings.worker_id,
                        level=log.get("level", "INFO"),
                        message=log.get("message", ""),
                        source=log.get("source", "worker"),
                        timestamp=log.get("timestamp", time.time()),
                        metadata=log.get("metadata", {})
                    )
            
            response = self.stub.SendLogs(log_generator())
            print(f"[gRPC] ✓ Sent {response.received_count} logs")
            return response.success
            
        except Exception as e:
            print(f"[gRPC] Error sending logs: {e}")
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
            print(f"[gRPC] ✓ Sent {response.received_count} metrics")
            return response.success
            
        except Exception as e:
            print(f"[gRPC] Error sending metrics: {e}")
            return False
    
    def get_config(self) -> Optional[Dict[str, str]]:
        """Get configuration from master."""
        try:
            request = worker_pb2.GetConfigRequest(worker_id=settings.worker_id)
            response = self.stub.GetConfig(request)
            if response.success:
                config_dict = dict(response.config)
                # 应用配置到 settings
                try:
                    settings.update_from_dict(config_dict)
                    print(f"[gRPC] Applied config from master")
                except Exception as e:
                    print(f"[gRPC] Error applying config: {e}")
                return config_dict
            return None
        except Exception as e:
            print(f"[gRPC] Error getting config: {e}")
            return None
    
    def _start_communicate_stream(self):
        """Internal method to run the bidirectional stream."""
        try:
            def message_generator():
                # Send initial ping
                ping = worker_pb2.Ping(sequence=1, timestamp=time.time())
                yield worker_pb2.WorkerMessage(ping=ping)
                
                # Keep alive - send pings periodically
                seq = 2
                while self._communicate_running:
                    time.sleep(30)
                    if self._communicate_running:
                        ping = worker_pb2.Ping(sequence=seq, timestamp=time.time())
                        yield worker_pb2.WorkerMessage(ping=ping)
                        seq += 1
            
            # Start the stream
            responses = self.stub.Communicate(message_generator())
            
            # Process responses from master
            for master_msg in responses:
                if master_msg.HasField("pong"):
                    print(f"[gRPC] Received pong from master: seq={master_msg.pong.sequence}")
                elif master_msg.HasField("config_update"):
                    config_dict = dict(master_msg.config_update.config)
                    print(f"[gRPC] Received config update: {config_dict}")
                    # 动态应用配置
                    try:
                        settings.update_from_dict(config_dict)
                        print(f"[gRPC] Applied config update")
                    except Exception as e:
                        print(f"[gRPC] Error applying config update: {e}")
                elif master_msg.HasField("task_update"):
                    print(f"[gRPC] Received task update: {master_msg.task_update.action}")
                elif master_msg.HasField("trade_day_data"):
                    print(f"[gRPC] Received trade day data: {list(master_msg.trade_day_data.trade_days)}")
            
        except Exception as e:
            print(f"[gRPC] Error in communicate stream: {e}")
    
    def start_communicate_stream(self):
        """Start bidirectional streaming communication."""
        if not self._communicate_running:
            self._communicate_running = True
            self._communicate_thread = threading.Thread(
                target=self._start_communicate_stream,
                daemon=True
            )
            self._communicate_thread.start()
            print("[gRPC] Started bidirectional communication stream")
    
    def _stop_communicate_stream(self):
        """Stop bidirectional streaming."""
        self._communicate_running = False
        if self._communicate_thread and self._communicate_thread.is_alive():
            self._communicate_thread.join(timeout=2)


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
    health_status = "✓ Healthy" if healthy else "✗ Unhealthy"
    print(f"    Master health: {health_status}")
    
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
