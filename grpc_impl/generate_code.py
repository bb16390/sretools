#!/usr/bin/env python3
"""Generate gRPC Python code from proto file."""

import os
import sys
import subprocess
import shutil

def main():
    # Get directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    proto_file = os.path.join(script_dir, "worker.proto")
    
    print(f"Generating gRPC code from: {proto_file}")
    
    # Remove old generated files
    for f in os.listdir(script_dir):
        if f.endswith("_pb2.py") or f.endswith("_pb2_grpc.py"):
            os.remove(os.path.join(script_dir, f))
            print(f"Removed old file: {f}")
    
    # Command to generate Python code
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"--proto_path={script_dir}",
        f"--python_out={script_dir}",
        f"--grpc_python_out={script_dir}",
        proto_file
    ]
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        print("✓ Successfully generated code!")
        
        # Fix imports
        pb2_file = os.path.join(script_dir, "worker_pb2.py")
        grpc_file = os.path.join(script_dir, "worker_pb2_grpc.py")
        
        if os.path.exists(grpc_file):
            with open(grpc_file, "r") as f:
                content = f.read()
            
            # Fix the import
            content = content.replace(
                "import worker_pb2 as worker__pb2",
                "from . import worker_pb2 as worker__pb2"
            )
            
            with open(grpc_file, "w") as f:
                f.write(content)
            
            print("✓ Fixed imports!")
        
        # List generated files
        print("\nGenerated files:")
        for f in sorted(os.listdir(script_dir)):
            if f.endswith("_pb2.py") or f.endswith("_pb2_grpc.py"):
                print(f"  - {f}")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to generate code: {e}", file=sys.stderr)
        if e.stdout:
            print(f"  Stdout: {e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"  Stderr: {e.stderr}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
