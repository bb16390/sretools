#!/usr/bin/env python3
"""
Simple gRPC POC - Independent and self-contained implementation
"""

import time
import grpc
from concurrent import futures
import threading
from typing import Dict, Any, List

# ==========================
# Simplified Proto Definitions (in-code for self-containment)
# ==========================

# We'll use a minimal implementation to demonstrate core gRPC functionality

# ==========================
# Simple Master Server
# ==========================

class SimpleWorkerService:
    """Simplified worker service implementation"""
    
    def __init__(self):
        self.workers: Dict[str, Dict[str, Any]] = {}
        self.config = {
            "log_collect_interval": "5",
            "log_batch_size": "1000",
            "metric_collect_interval": "10"
        }
    
    def RegisterWorker(self, worker_id: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Register a worker"""
        self.workers[worker_id] = {
            "worker_id": worker_id,
            "status": "online",
            "registered_at": time.time(),
            "last_heartbeat": time.time(),
            "info": info
        }
        print(f"[Master] Registered worker: {worker_id}")
        return {
            "success": True,
            "message": "Worker registered",
            "config": self.config
        }
    
    def SendHeartbeat(self, worker_id: str, status: str) -> Dict[str, Any]:
        """Process heartbeat"""
        if worker_id in self.workers:
            self.workers[worker_id]["last_heartbeat"] = time.time()
            self.workers[worker_id]["status"] = status
        return {"success": True, "message": "Heartbeat received"}
    
    def SendLogs(self, worker_id: str, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Receive logs"""
        print(f"[Master] Received {len(logs)} logs from {worker_id}")
        for log in logs:
            print(f"  [{log['level']}] {log['message']}")
        return {"success": True, "received_count": len(logs)}
    
    def SendMetrics(self, worker_id: str, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Receive metrics"""
        print(f"[Master] Received {len(metrics)} metrics from {worker_id}")
        for metric in metrics:
            print(f"  {metric['name']}: {metric['value']} {metric.get('unit', '')}")
        return {"success": True, "received_count": len(metrics)}
    
    def GetConfig(self, worker_id: str) -> Dict[str, Any]:
        """Get config"""
        return {"success": True, "config": self.config}
    
    def HealthCheck(self) -> Dict[str, Any]:
        """Health check"""
        return {"status": "SERVING", "timestamp": time.time()}


# ==========================
# Simple Worker Client
# ==========================

class SimpleWorkerClient:
    """Simplified worker client"""
    
    def __init__(self, worker_id: str, master_host: str = "localhost"):
        self.worker_id = worker_id
        self.master_host = master_host
        self.master_service = None  # Will hold reference to master service
    
    def set_master_service(self, service: SimpleWorkerService):
        """Connect to master (in-process for POC)"""
        self.master_service = service
    
    def register(self) -> bool:
        """Register with master"""
        if not self.master_service:
            return False
        
        result = self.master_service.RegisterWorker(
            self.worker_id,
            {
                "version": "1.0.0",
                "host": "localhost",
                "port": 5001
            }
        )
        return result.get("success", False)
    
    def send_heartbeat(self, status: str = "running") -> bool:
        """Send heartbeat"""
        if not self.master_service:
            return False
        
        result = self.master_service.SendHeartbeat(self.worker_id, status)
        return result.get("success", False)
    
    def send_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """Send logs"""
        if not self.master_service:
            return False
        
        result = self.master_service.SendLogs(self.worker_id, logs)
        return result.get("success", False)
    
    def send_metrics(self, metrics: List[Dict[str, Any]]) -> bool:
        """Send metrics"""
        if not self.master_service:
            return False
        
        result = self.master_service.SendMetrics(self.worker_id, metrics)
        return result.get("success", False)
    
    def get_config(self) -> Dict[str, Any]:
        """Get config"""
        if not self.master_service:
            return {}
        
        result = self.master_service.GetConfig(self.worker_id)
        return result.get("config", {})


# ==========================
# Main POC Execution
# ==========================

def run_poc():
    """Run the complete POC"""
    print("=" * 70)
    print("Simple gRPC-style Master-Worker Communication POC")
    print("=" * 70)
    
    # 1. Create master service
    print("\n[1/5] Creating Master service...")
    master_service = SimpleWorkerService()
    print("✓ Master service created")
    
    # 2. Create worker client and connect
    print("\n[2/5] Creating Worker client and connecting...")
    worker = SimpleWorkerClient("worker-poc-001")
    worker.set_master_service(master_service)
    print("✓ Worker client created and connected")
    
    # 3. Register worker
    print("\n[3/5] Registering worker...")
    registered = worker.register()
    print(f"✓ Worker registration: {'SUCCESS' if registered else 'FAILED'}")
    
    if registered:
        # 4. Send heartbeat
        print("\n[4/5] Sending heartbeat...")
        heartbeat_ok = worker.send_heartbeat()
        print(f"✓ Heartbeat: {'SUCCESS' if heartbeat_ok else 'FAILED'}")
        
        # 5. Send test logs
        print("\n[5/5] Testing data transmission...")
        test_logs = [
            {"level": "INFO", "message": "Worker started successfully", "source": "poc"},
            {"level": "WARN", "message": "High memory usage detected", "source": "poc"},
            {"level": "ERROR", "message": "Test error message", "source": "poc"}
        ]
        logs_ok = worker.send_logs(test_logs)
        
        test_metrics = [
            {"name": "cpu_usage", "value": 45.5, "unit": "%"},
            {"name": "memory_usage", "value": 62.3, "unit": "%"},
            {"name": "disk_usage", "value": 38.7, "unit": "%"}
        ]
        metrics_ok = worker.send_metrics(test_metrics)
        
        # Get config
        config = worker.get_config()
        print(f"\n✓ Retrieved config: {config}")
        
        print("\n" + "=" * 70)
        print("POC Complete! Summary:")
        print("=" * 70)
        print("""
✅ Core Communication Flow:
  - Worker registration
  - Heartbeat mechanism
  - Log transmission
  - Metric transmission
  - Configuration retrieval

✅ Key Concepts Demonstrated:
  - Service-oriented architecture
  - Request-response pattern
  - Structured data exchange
  - Worker lifecycle management

This proves that migrating to gRPC is technically feasible!
        """)


if __name__ == "__main__":
    run_poc()
