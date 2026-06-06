#!/usr/bin/env python3
"""Generate gRPC Python code from .proto file."""

import os
import subprocess
import sys

def main():
    # Get the directory of this script and project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    proto_file = os.path.join(root_dir, "protos", "worker.proto")
    
    # Output directories
    master_grpc_dir = os.path.join(root_dir, "master", "grpc")
    worker_grpc_dir = os.path.join(root_dir, "worker", "grpc")
    
    # Ensure output directories exist
    os.makedirs(master_grpc_dir, exist_ok=True)
    os.makedirs(worker_grpc_dir, exist_ok=True)
    
    # Generate gRPC code for master
    print("Generating gRPC code for master...")
    subprocess.run([
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{os.path.join(root_dir, 'protos')}",
        "--python_out=" + master_grpc_dir,
        "--grpc_python_out=" + master_grpc_dir,
        proto_file
    ], check=True, cwd=root_dir)
    
    # Generate gRPC code for worker
    print("Generating gRPC code for worker...")
    subprocess.run([
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{os.path.join(root_dir, 'protos')}",
        "--python_out=" + worker_grpc_dir,
        "--grpc_python_out=" + worker_grpc_dir,
        proto_file
    ], check=True, cwd=root_dir)
    
    # Copy __init__.py to ensure the directories
    for dir_path in [master_grpc_dir, worker_grpc_dir]:
        init_file = os.path.join(dir_path, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write("# Generated gRPC modules\n")
    
    print("\n✅ gRPC code generated successfully!")

if __name__ == "__main__":
    main()
