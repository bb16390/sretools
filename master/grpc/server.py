"""
gRPC Server implementation for Master - Worker Communication.
This runs in parallel with the existing HTTP/REST API.
"""

import time
import grpc
import threading
from concurrent import futures
from typing import Dict, Any, List

import sys
import os

# Add the current directory to path for gRPC modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core.settings import settings
    from core.security import verify_signature, SECRET_KEY
except ImportError:
    # Fallback if not running in the full project context
    SECRET_KEY = "test-secret-key"

import worker_pb2
import worker_pb2_grpc


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
        # Store bidirectional streams for pushing updates
        self.active_streams: Dict[str, Any] = {}
    
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
        """Bidirectional streaming for real-time communication."""
        worker_id = "unknown"
        
        try:
            # First message identifies the worker
            first_message = True
            
            for worker_msg in request_iterator:
                if first_message:
                    # Try to get worker_id from the message metadata or first message
                    worker_id = "stream-worker-" + str(int(time.time()))
                    self.active_streams[worker_id] = context
                    first_message = False
                    print(f"[gRPC] Bidirectional stream established for worker {worker_id}")
                
                if worker_msg.HasField("ping"):
                    # Respond with pong
                    pong = worker_pb2.Pong(
                        sequence=worker_msg.ping.sequence,
                        timestamp=time.time()
                    )
                    master_msg = worker_pb2.MasterMessage(pong=pong)
                    yield master_msg
                
                elif worker_msg.HasField("config_ack"):
                    print(f"[gRPC] Received config ack from worker {worker_id}")
                
                elif worker_msg.HasField("task_status"):
                    print(f"[gRPC] Received task status from worker {worker_id}: {worker_msg.task_status.status}")
                
        except Exception as e:
            print(f"[gRPC] Error in bidirectional stream: {e}")
        
        finally:
            if worker_id in self.active_streams:
                del self.active_streams[worker_id]
                print(f"[gRPC] Bidirectional stream closed for worker {worker_id}")


# Global server instance
_grpc_server = None


def start_grpc_server(port: int = 50051, daemon: bool = True):
    """Start the gRPC server in a background thread."""
    global _grpc_server
    
    if _grpc_server:
        print("gRPC Server already running")
        return
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    worker_pb2_grpc.add_WorkerServiceServicer_to_server(WorkerServiceServicer(), server)
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
    global _grpc_server
    if _grpc_server:
        print("Stopping gRPC server...")
        _grpc_server.stop(0)
        _grpc_server = None


if __name__ == "__main__":
    start_grpc_server(daemon=False)
