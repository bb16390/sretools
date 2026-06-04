"""
gRPC Client implementation for Worker.
"""

import time
import grpc
import threading
from typing import Dict, Any, Optional, List, Iterator

from worker.grpc import worker_pb2
from worker.grpc import worker_pb2_grpc
from worker.core.settings import settings
from worker.core.auth import generate_signature


class CentralGrpcClient:
    """gRPC client for communicating with master."""
    
    def __init__(self, server_address: str = "localhost:50051"):
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self.connected = False
        self.registered = False
        
        # Create channel and stub
        self._connect()
    
    def _connect(self):
        """Connect to gRPC server."""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = worker_pb2_grpc.WorkerServiceStub(self.channel)
            self.connected = True
            print(f"Connected to gRPC server at {self.server_address}")
        except Exception as e:
            print(f"Failed to connect to gRPC server: {e}")
            self.connected = False
    
    def close(self):
        """Close the connection."""
        if self.channel:
            self.channel.close()
            self.connected = False
            print("gRPC connection closed")
    
    def register_worker(self) -> bool:
        """Register worker with master."""
        if not self.connected:
            print("Not connected to server")
            return False
        
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
                print(f"Successfully registered as {response.worker_id}")
                # Save config
                if response.config:
                    print("Received config:", response.config)
                return True
            else:
                print(f"Registration failed: {response.message}")
                return False
        
        except Exception as e:
            print(f"Error registering worker: {e}")
            return False
    
    def send_heartbeat(self, status: str = "running") -> bool:
        """Send heartbeat to master."""
        if not self.connected:
            return False
        
        try:
            # Generate signature
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
            print(f"Error sending heartbeat: {e}")
            return False
    
    def send_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """Send logs to master (client streaming)."""
        if not self.connected:
            return False
        
        try:
            def log_generator():
                for log in logs:
                    yield worker_pb2.LogEntry(
                        worker_id=settings.worker_id,
                        level=log.get("level", "INFO"),
                        message=log.get("message", ""),
                        source=log.get("source", "unknown"),
                        timestamp=log.get("timestamp", time.time()),
                        metadata=log.get("metadata", {})
                    )
            
            response = self.stub.SendLogs(log_generator())
            print(f"Sent {response.received_count} logs")
            return response.success
        
        except Exception as e:
            print(f"Error sending logs: {e}")
            return False
    
    def send_metrics(self, metrics: List[Dict[str, Any]]) -> bool:
        """Send metrics to master (client streaming)."""
        if not self.connected:
            return False
        
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
            print(f"Sent {response.received_count} metrics")
            return response.success
        
        except Exception as e:
            print(f"Error sending metrics: {e}")
            return False
    
    def get_config(self) -> Optional[Dict[str, str]]:
        """Get configuration from master."""
        if not self.connected:
            return None
        
        try:
            request = worker_pb2.GetConfigRequest(worker_id=settings.worker_id)
            response = self.stub.GetConfig(request)
            
            if response.success:
                return dict(response.config)
            return None
        
        except Exception as e:
            print(f"Error getting config: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check if master is healthy."""
        if not self.connected:
            return False
        
        try:
            request = worker_pb2.HealthCheckRequest(service="worker")
            response = self.stub.HealthCheck(request)
            return response.status == worker_pb2.HealthCheckResponse.SERVING
        
        except Exception as e:
            print(f"Health check failed: {e}")
            return False
    
    def start_communicate_stream(self):
        """Start bidirectional streaming communication."""
        if not self.connected:
            print("Not connected")
            return
        
        def stream_worker():
            # Send initial ping
            yield worker_pb2.WorkerMessage(
                ping=worker_pb2.Ping(sequence=1, timestamp=time.time())
            )
        
        try:
            responses = self.stub.Communicate(stream_worker())
            for response in responses:
                if response.HasField("pong"):
                    print(f"Received pong: sequence={response.pong.sequence}")
                elif response.HasField("config_update"):
                    print(f"Received config update: {response.config_update.config}")
                elif response.HasField("task_update"):
                    print(f"Received task update: {response.task_update.action}")
                elif response.HasField("trade_day_data"):
                    print(f"Received trade days: {response.trade_day_data.trade_days}")
        
        except Exception as e:
            print(f"Error in communicate stream: {e}")


def main():
    """Test the gRPC client."""
    client = CentralGrpcClient()
    
    # Test health check
    print("\n1. Testing health check...")
    healthy = client.health_check()
    print(f"Health check: {'OK' if healthy else 'FAILED'}")
    
    # Test registration
    print("\n2. Testing registration...")
    registered = client.register_worker()
    print(f"Registration: {'OK' if registered else 'FAILED'}")
    
    # Test heartbeat
    if registered:
        print("\n3. Testing heartbeat...")
        heartbeat_ok = client.send_heartbeat()
        print(f"Heartbeat: {'OK' if heartbeat_ok else 'FAILED'}")
        
        # Test sending logs
        print("\n4. Testing sending logs...")
        test_logs = [
            {"level": "INFO", "message": "Test log 1", "source": "test"},
            {"level": "WARN", "message": "Test log 2", "source": "test"}
        ]
        logs_ok = client.send_logs(test_logs)
        print(f"Send logs: {'OK' if logs_ok else 'FAILED'}")
        
        # Test sending metrics
        print("\n5. Testing sending metrics...")
        test_metrics = [
            {"name": "cpu_usage", "value": 45.5, "unit": "%"},
            {"name": "memory_usage", "value": 62.3, "unit": "%"}
        ]
        metrics_ok = client.send_metrics(test_metrics)
        print(f"Send metrics: {'OK' if metrics_ok else 'FAILED'}")
        
        # Test get config
        print("\n6. Testing get config...")
        config = client.get_config()
        if config:
            print(f"Got config: {config}")
    
    client.close()


if __name__ == "__main__":
    main()
