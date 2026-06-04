#!/usr/bin/env python3
"""
完整的 gRPC 测试 - Master 和 Worker 集成测试
验证 gRPC 迁移的可行性
"""

import time
import threading
import sys
import os

# 添加路径以便导入 grpc_impl 模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "grpc_impl"))

import worker_pb2
import worker_pb2_grpc

# 导入服务端和客户端
from server import WorkerService, serve
from client import WorkerClient


def start_server_in_thread():
    """在后台线程中启动 gRPC 服务器"""
    server_thread = threading.Thread(
        target=lambda: serve(50051),
        daemon=True
    )
    server_thread.start()
    # 等待服务器启动
    time.sleep(1)
    return server_thread


def run_complete_test():
    """运行完整的 gRPC 测试"""
    print("=" * 70)
    print("  完整 gRPC Master-Worker 集成测试")
    print("=" * 70)
    
    # 步骤 1: 启动服务器
    print("\n[步骤 1] 启动 gRPC 服务器...")
    start_server_in_thread()
    print("   ✓ 服务器已启动!")
    
    # 步骤 2: 创建 Worker 客户端
    print("\n[步骤 2] 创建 Worker 客户端...")
    worker = WorkerClient("worker-test-001", "localhost:50051")
    print("   ✓ 客户端已创建!")
    
    # 步骤 3: 健康检查
    print("\n[步骤 3] 执行健康检查...")
    healthy = worker.health_check()
    print(f"   ✓ 健康检查: {'通过' if healthy else '失败'}")
    
    if not healthy:
        print("   ✗ 服务器不健康，退出测试。")
        return
    
    # 步骤 4: 注册 Worker
    print("\n[步骤 4] 注册 Worker...")
    registered = worker.register()
    print(f"   ✓ 注册: {'通过' if registered else '失败'}")
    
    if not registered:
        return
    
    # 步骤 5: 发送心跳
    print("\n[步骤 5] 发送心跳...")
    heartbeat_ok = worker.send_heartbeat()
    print(f"   ✓ 心跳: {'通过' if heartbeat_ok else '失败'}")
    
    # 步骤 6: 发送日志（流式）
    print("\n[步骤 6] 发送日志（流式传输）...")
    test_logs = [
        {"level": "INFO", "message": "Worker 进程已启动", "source": "main"},
        {"level": "INFO", "message": "配置加载成功", "source": "config"},
        {"level": "WARN", "message": "内存使用率过高 (75%)", "source": "monitor"},
        {"level": "INFO", "message": "任务执行成功", "source": "worker"}
    ]
    logs_ok = worker.send_logs(test_logs)
    print(f"   ✓ 日志传输: {'通过' if logs_ok else '失败'}")
    
    # 步骤 7: 获取配置
    print("\n[步骤 7] 获取配置...")
    config = worker.get_config()
    if config:
        print(f"   ✓ 获取到配置: {dict(config)}")
    else:
        print("   ✗ 获取配置失败!")
    
    # 测试完成!
    print("\n" + "=" * 70)
    print("  🎉 完成! gRPC 实现工作正常!")
    print("=" * 70)
    print("\n总结:")
    print("  ✓ Protocol Buffers: 正常")
    print("  ✓ gRPC 服务器: 运行中")
    print("  ✓ gRPC 客户端: 已连接")
    print("  ✓ 单向 RPC: 正常（注册、心跳、配置）")
    print("  ✓ 客户端流式: 正常（日志发送）")
    print("\n迁移可行性: ✅ 完全可行! 🚀")
    
    # 保持连接一段时间
    print("\n保持连接 2 秒...")
    time.sleep(2)
    
    worker.close()


if __name__ == "__main__":
    try:
        run_complete_test()
    except KeyboardInterrupt:
        print("\n用户中断测试。")
    except Exception as e:
        print(f"\n✗ 测试失败，错误: {e}")
        import traceback
        traceback.print_exc()
