#!/usr/bin/env python3
"""Generate gRPC Python code from .proto file.

生成后会自动把 ``*_pb2_grpc.py`` 中的裸 ``import worker_pb2``
修正为包内相对导入 ``from . import worker_pb2``，避免 ``master/grpc``
或 ``worker/grpc`` 目录被加入 ``sys.path`` 时遮蔽第三方 ``grpcio``
库导致 ``grpc.__version__`` 报错。
"""

import os
import re
import subprocess
import sys


def _patch_grpc_imports(grpc_dir: str) -> None:
    """修正 ``*_pb2_grpc.py`` 中的 ``import worker_pb2`` 为相对导入。"""
    pb2_grpc_file = os.path.join(grpc_dir, "worker_pb2_grpc.py")
    if not os.path.isfile(pb2_grpc_file):
        return
    with open(pb2_grpc_file, "r", encoding="utf-8") as f:
        content = f.read()
    # 把 "import worker_pb2 as worker__pb2" 替换成相对导入
    new_content = re.sub(
        r"^import\s+worker_pb2\s+as\s+worker__pb2\s*$",
        "from . import worker_pb2 as worker__pb2",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if new_content != content:
        with open(pb2_grpc_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  ✅ Patched imports in {os.path.relpath(pb2_grpc_file)}")


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

    # 修正生成代码的 import，避免包名遮蔽第三方 grpcio
    print("\nPatching generated imports for package-internal use...")
    _patch_grpc_imports(master_grpc_dir)
    _patch_grpc_imports(worker_grpc_dir)
    
    print("\n✅ gRPC code generated successfully!")

if __name__ == "__main__":
    main()
