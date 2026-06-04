"""gRPC Client for Worker - Master Communication."""

import time
import grpc
import sys
import os
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import worker_pb2
import worker_pb2_grpc


class WorkerClient:
    """gRPC Client for Worker."""
    
    def __init__(self, worker_id: str, server_address: str = "localhost:50051"):
        self.worker_id = worker_id
        self.server_address = server_address
        self.channel = None
        self.stub = None
        self.registered = False
        
        self._connect()
    
    def _connect(self):
        """Connect to gRPC server."""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = worker_pb2_grpc.WorkerServiceStub(self.channel)
            print(f"[Worker] Connected to {self.server_address}")
        except Exception as e:
            print(f"[Worker] Failed to connect: {e}")
    
    def close(self):
        """Close connection."""
        if self.channel:
            self.channel.close()
            print("[Worker] Connection closed")
    
    def register(self) -> bool:
        """Register with master."""
        try:
            info = worker_pb2.WorkerInfo(
                version="1.0.0",
                host="localhost",
                port=5001,
                timestamp=time.time()
            )
            
            request = worker_pb2.RegisterRequest(
                worker_id=self.worker_id,
                info=info,
                signature="dummy_signature"
            )
            
            response = self.stub.RegisterWorker(request)
            
            if response.success:
                self.registered = True
                print(f"[Worker] ✓ Registered successfully!")
                print(f"[Worker]   Received config: {dict(response.config)}")
                return True
            else:
                print(f"[Worker] Registration failed: {response.message}")
                return False
                
        except Exception as e:
            print(f"[Worker] Error registering: {e}")
            return False
    
    def send_heartbeat(self, status: str = "running") -> bool:
        """Send heartbeat."""
        try:
            request = worker_pb2.HeartbeatRequest(
                worker_id=self.worker_id,
                status=status,
                timestamp=time.time(),
                signature="dummy_signature"
            )
            response = self.stub.SendHeartbeat(request)
            return response.success
        except Exception as e:
            print(f"[Worker] Error sending heartbeat: {e}")
            return False
    
    def send_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """Send logs (streaming)."""
        try:
            def log_generator():
                for log in logs:
                    yield worker_pb2.LogEntry(
                        worker_id=self.worker_id,
                        level=log.get("level", "INFO"),
                        message=log.get("message", ""),
                        source=log.get("source", "worker"),
                        timestamp=log.get("timestamp", time.time()),
                        metadata=log.get("metadata", {})
                    )
            
            response = self.stub.SendLogs(log_generator())
            print(f"[Worker] ✓ Sent {response.received_count} logs")
            return response.success
            
        except Exception as e:
            print(f"[Worker] Error sending logs: {e}")
            return False
    
    def get_config(self) -> Dict[str, str]:
        """Get config from master."""
        try:
            request = worker_pb2.GetConfigRequest(worker_id=self.worker_id)
            response = self.stub.GetConfig(request)
            if response.success:
                return dict(response.config)
            return {}
        except Exception as e:
            print(f"[Worker] Error getting config: {e}")
            return {}
    
    def health_check(self) -> bool:
        """Check if master is healthy."""
        try:
            request = worker_pb2.HealthCheckRequest(service="worker")
            response = self.stub.HealthCheck(request)
            return response.status == worker_pb2.HealthCheckResponse.SERVING
        except Exception as e:
            print(f"[Worker] Health check failed: {e}")
            return False


def run_demo():
    """Run a complete demo."""
    print("=" * 60)
    print("gRPC Worker Client Demo")
    print("=" * 60)
    
    # Create client
    print("\n1. Creating worker client...")
    client = WorkerClient("worker-poc-001", "localhost:50051")
    
    # Health check
    print("\n2. Health check...")
    healthy = client.health_check()
    print(f"   ✓ Master is {'healthy' if healthy else 'not healthy'}")
    
    if healthy:
        # Register
        print("\n3. Registering worker...")
        registered = client.register()
        
        if registered:
            # Heartbeat
            print("\n4. Sending heartbeat...")
            heartbeat_ok = client.send_heartbeat()
            print(f"   ✓ Heartbeat: {'OK' if heartbeat_ok else 'FAILED'}")
            
            # Send logs
            print("\n5. Sending test logs...")
            test_logs = [
                {"level": "INFO", "message": "Worker started", "source": "main"},
                {"level": "WARN", "message": "High CPU usage detected", "source": "monitor"},
                {"level": "INFO", "message": "Processing completed", "source": "worker"}
            ]
            logs_ok = client.send_logs(test_logs)
            print(f"   ✓ Logs: {'OK' if logs_ok else 'FAILED'}")
            
            # Get config
            print("\n6. Getting config...")
            config = client.get_config()
            if config:
                print(f"   ✓ Config: {config}")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
    
    client.close()


if __name__ == "__main__":
    run_demo()
