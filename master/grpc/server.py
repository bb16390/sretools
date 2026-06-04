"""
gRPC Server implementation for Master.
"""

import time
import grpc
from concurrent import futures
from typing import Dict, Any, List

from master.grpc import worker_pb2
from master.grpc import worker_pb2_grpc
from core.security import verify_signature, SECRET_KEY


# In-memory storage for workers and connections
workers: Dict[str, Dict[str, Any]] = {}
worker_connections: Dict[str, Any] = {}

# Default worker config
default_worker_config = {
    "log_collect_interval": "5",
    "log_batch_size": "1000",
    "log_queue_size": "10000",
    "metric_collect_interval": "10",
    "metric_batch_size": "500"
}


class WorkerServiceServicer(worker_pb2_grpc.WorkerServiceServicer):
    """Implementation of WorkerService."""
    
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
        
        print(f"Worker {worker_id} registered successfully")
        
        return worker_pb2.RegisterResponse(
            success=True,
            message="Worker registered successfully",
            worker_id=worker_id,
            config=default_worker_config,
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
            context.set_details("Worker not found")
            return worker_pb2.HeartbeatResponse(
                success=False,
                message="Worker not registered",
                timestamp=time.time()
            )
        
        # Update worker status
        workers[worker_id]["last_heartbeat"] = time.time()
        workers[worker_id]["status"] = request.status
        
        return worker_pb2.HeartbeatResponse(
            success=True,
            message="Heartbeat received",
            timestamp=time.time()
        )
    
    def SendLogs(self, request_iterator, context):
        """Receive logs from worker (client streaming)."""
        log_count = 0
        worker_id = None
        
        try:
            for log_entry in request_iterator:
                if worker_id is None:
                    worker_id = log_entry.worker_id
                
                log_count += 1
                # Here you would process/store the log
                print(f"Received log from {log_entry.worker_id}: {log_entry.message}")
        
        except Exception as e:
            print(f"Error receiving logs: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
        
        return worker_pb2.SendLogsResponse(
            success=True,
            message=f"Received {log_count} logs",
            received_count=log_count,
            timestamp=time.time()
        )
    
    def SendMetrics(self, request_iterator, context):
        """Receive metrics from worker (client streaming)."""
        metric_count = 0
        worker_id = None
        
        try:
            for metric_entry in request_iterator:
                if worker_id is None:
                    worker_id = metric_entry.worker_id
                
                metric_count += 1
                # Here you would process/store the metric
                print(f"Received metric from {metric_entry.worker_id}: {metric_entry.name} = {metric_entry.value}")
        
        except Exception as e:
            print(f"Error receiving metrics: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
        
        return worker_pb2.SendMetricsResponse(
            success=True,
            message=f"Received {metric_count} metrics",
            received_count=metric_count,
            timestamp=time.time()
        )
    
    def GetConfig(self, request, context):
        """Get configuration for worker."""
        return worker_pb2.GetConfigResponse(
            success=True,
            config=default_worker_config,
            timestamp=time.time()
        )
    
    def HealthCheck(self, request, context):
        """Health check endpoint."""
        return worker_pb2.HealthCheckResponse(
            status=worker_pb2.HealthCheckResponse.SERVING,
            timestamp=time.time()
        )
    
    def Communicate(self, request_iterator, context):
        """Bidirectional streaming for real-time communication."""
        worker_id = "unknown"
        
        try:
            # Process messages from worker
            for worker_msg in request_iterator:
                if worker_msg.HasField("ping"):
                    # Respond with pong
                    pong = worker_pb2.Pong(
                        sequence=worker_msg.ping.sequence,
                        timestamp=time.time()
                    )
                    master_msg = worker_pb2.MasterMessage(pong=pong)
                    yield master_msg
                
                elif worker_msg.HasField("config_ack"):
                    print(f"Received config ack from worker")
                
                elif worker_msg.HasField("task_status"):
                    print(f"Received task status: {worker_msg.task_status.status}")
        
        except Exception as e:
            print(f"Error in bidirectional stream: {e}")


def serve(port: int = 50051):
    """Start the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    worker_pb2_grpc.add_WorkerServiceServicer_to_server(
        WorkerServiceServicer(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    
    print(f"gRPC Server started on port {port}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("Shutting down gRPC server...")
        server.stop(0)


if __name__ == "__main__":
    serve()
