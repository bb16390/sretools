"""gRPC Server for Master - Worker Communication."""

import time
import grpc
from concurrent import futures
from typing import Dict, Any

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import worker_pb2
import worker_pb2_grpc


class WorkerService(worker_pb2_grpc.WorkerServiceServicer):
    """Implementation of WorkerService."""
    
    def __init__(self):
        self.workers: Dict[str, Dict[str, Any]] = {}
        self.default_config = {
            "log_collect_interval": "5",
            "log_batch_size": "1000",
            "log_queue_size": "10000",
            "metric_collect_interval": "10",
            "metric_batch_size": "500"
        }
    
    def RegisterWorker(self, request, context):
        """Register a worker."""
        worker_id = request.worker_id
        print(f"[Master] Registering worker: {worker_id}")
        
        self.workers[worker_id] = {
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
        
        return worker_pb2.RegisterResponse(
            success=True,
            message="Worker registered successfully",
            worker_id=worker_id,
            config=self.default_config,
            timestamp=time.time()
        )
    
    def SendHeartbeat(self, request, context):
        """Process heartbeat."""
        worker_id = request.worker_id
        print(f"[Master] Heartbeat from: {worker_id}")
        
        if worker_id in self.workers:
            self.workers[worker_id]["last_heartbeat"] = time.time()
            self.workers[worker_id]["status"] = request.status
            return worker_pb2.HeartbeatResponse(
                success=True,
                message="Heartbeat received",
                timestamp=time.time()
            )
        else:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return worker_pb2.HeartbeatResponse(
                success=False,
                message="Worker not found",
                timestamp=time.time()
            )
    
    def SendLogs(self, request_iterator, context):
        """Receive logs (streaming)."""
        received_count = 0
        worker_id = None
        
        try:
            for log_entry in request_iterator:
                if worker_id is None:
                    worker_id = log_entry.worker_id
                received_count += 1
                print(f"[Master] Log from {log_entry.worker_id}: [{log_entry.level}] {log_entry.message}")
        except Exception as e:
            print(f"[Master] Error receiving logs: {e}")
        
        return worker_pb2.SendLogsResponse(
            success=True,
            message=f"Received {received_count} logs",
            received_count=received_count,
            timestamp=time.time()
        )
    
    def GetConfig(self, request, context):
        """Get worker config."""
        print(f"[Master] Config requested by: {request.worker_id}")
        return worker_pb2.GetConfigResponse(
            success=True,
            config=self.default_config,
            timestamp=time.time()
        )
    
    def HealthCheck(self, request, context):
        """Health check."""
        return worker_pb2.HealthCheckResponse(
            status=worker_pb2.HealthCheckResponse.SERVING,
            timestamp=time.time()
        )


def serve(port: int = 50051):
    """Start the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    worker_pb2_grpc.add_WorkerServiceServicer_to_server(WorkerService(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    
    print(f"✅ Master gRPC Server started on port {port}")
    print("   Ready to accept worker connections...")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop(0)


if __name__ == "__main__":
    serve()
