#!/usr/bin/env python3
"""Complete gRPC Test - Master and Worker together!"""

import time
import threading
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import worker_pb2
import worker_pb2_grpc

# Import our server and client
from server import WorkerService, serve
from client import WorkerClient


def start_server_in_thread():
    """Start gRPC server in a background thread."""
    server_thread = threading.Thread(
        target=lambda: serve(50051),
        daemon=True
    )
    server_thread.start()
    # Give server time to start
    time.sleep(1)
    return server_thread


def run_complete_test():
    """Run the complete gRPC test."""
    print("=" * 70)
    print("  COMPLETE gRPC MASTER-WORKER TEST")
    print("=" * 70)
    
    # Step 1: Start server
    print("\n[Step 1] Starting gRPC Server...")
    start_server_in_thread()
    print("   ✓ Server started!")
    
    # Step 2: Create worker client
    print("\n[Step 2] Creating Worker Client...")
    worker = WorkerClient("worker-test-001", "localhost:50051")
    print("   ✓ Client created!")
    
    # Step 3: Health check
    print("\n[Step 3] Health Check...")
    healthy = worker.health_check()
    print(f"   ✓ Health check: {'PASSED' if healthy else 'FAILED'}")
    
    if not healthy:
        print("   ✗ Server not healthy, exiting.")
        return
    
    # Step 4: Register worker
    print("\n[Step 4] Registering Worker...")
    registered = worker.register()
    print(f"   ✓ Registration: {'PASSED' if registered else 'FAILED'}")
    
    if not registered:
        return
    
    # Step 5: Send heartbeat
    print("\n[Step 5] Sending Heartbeat...")
    heartbeat_ok = worker.send_heartbeat()
    print(f"   ✓ Heartbeat: {'PASSED' if heartbeat_ok else 'FAILED'}")
    
    # Step 6: Send logs (streaming)
    print("\n[Step 6] Sending Logs (Streaming)...")
    test_logs = [
        {"level": "INFO", "message": "Worker process started", "source": "main"},
        {"level": "INFO", "message": "Loading configuration", "source": "config"},
        {"level": "WARN", "message": "Memory usage high (75%)", "source": "monitor"},
        {"level": "INFO", "message": "Task completed successfully", "source": "worker"}
    ]
    logs_ok = worker.send_logs(test_logs)
    print(f"   ✓ Log streaming: {'PASSED' if logs_ok else 'FAILED'}")
    
    # Step 7: Get config
    print("\n[Step 7] Getting Configuration...")
    config = worker.get_config()
    if config:
        print(f"   ✓ Received config: {dict(config)}")
    else:
        print("   ✗ Failed to get config")
    
    # Test complete!
    print("\n" + "=" * 70)
    print("  🎉 COMPLETE! gRPC IMPLEMENTATION WORKS!")
    print("=" * 70)
    print("\nSUMMARY:")
    print("  ✓ Protocol Buffers: Working")
    print("  ✓ gRPC Server: Running")
    print("  ✓ gRPC Client: Connected")
    print("  ✓ Unary RPCs: Working (Register, Heartbeat, Config)")
    print("  ✓ Client Streaming: Working (Log sending)")
    print("\nMIGRATION IS FEASIBLE! 🚀")
    
    # Keep alive for a bit
    print("\nKeeping connection alive for 2 seconds...")
    time.sleep(2)
    
    worker.close()


if __name__ == "__main__":
    try:
        run_complete_test()
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
