#!/usr/bin/env python3
"""
Script to generate gRPC Python code from .proto files.
"""

import os
import sys
import subprocess
import shutil


def main():
    # Get project root directory
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # Paths
    proto_dir = os.path.join(project_root, "protos")
    out_dir_master = os.path.join(project_root, "master", "grpc")
    out_dir_worker = os.path.join(project_root, "worker", "grpc")
    
    # Create output directories
    os.makedirs(out_dir_master, exist_ok=True)
    os.makedirs(out_dir_worker, exist_ok=True)
    
    # Create __init__.py files
    for out_dir in [out_dir_master, out_dir_worker]:
        init_file = os.path.join(out_dir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write('"""Generated gRPC code."""\n')
    
    # Find all .proto files
    proto_files = [
        os.path.join(proto_dir, f)
        for f in os.listdir(proto_dir)
        if f.endswith(".proto")
    ]
    
    if not proto_files:
        print(f"No .proto files found in {proto_dir}", file=sys.stderr)
        return 1
    
    print(f"Found {len(proto_files)} .proto file(s):")
    for proto_file in proto_files:
        print(f"  - {os.path.basename(proto_file)}")
    
    # Generate code for each proto file
    for proto_file in proto_files:
        print(f"\nGenerating code for {os.path.basename(proto_file)}...")
        
        # Command to generate Python code
        cmd = [
            sys.executable, "-m", "grpc_tools.protoc",
            f"--proto_path={proto_dir}",
            f"--python_out={out_dir_master}",
            f"--grpc_python_out={out_dir_master}",
            f"--python_out={out_dir_worker}",
            f"--grpc_python_out={out_dir_worker}",
            proto_file
        ]
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            print(f"✓ Successfully generated code")
            if result.stdout:
                print(f"  Output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to generate code: {e}", file=sys.stderr)
            if e.stdout:
                print(f"  Stdout: {e.stdout}", file=sys.stderr)
            if e.stderr:
                print(f"  Stderr: {e.stderr}", file=sys.stderr)
            return 1
    
    # Fix imports - remove relative imports for direct usage
    for out_dir in [out_dir_master, out_dir_worker]:
        grpc_file = os.path.join(out_dir, "worker_pb2_grpc.py")
        if os.path.exists(grpc_file):
            with open(grpc_file, "r") as f:
                content = f.read()
            
            # Replace relative import with absolute
            content = content.replace(
                "from . import worker_pb2 as worker__pb2",
                "import worker_pb2 as worker__pb2"
            )
            
            with open(grpc_file, "w") as f:
                f.write(content)
            
            print(f"\n✓ Fixed imports in {os.path.basename(grpc_file)}")
    
    print("\n✅ All code generated successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
