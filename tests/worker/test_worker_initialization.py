#!/usr/bin/env python3
"""测试 Worker 类的初始化过程"""

import sys
import os
import logging
import io
from contextlib import redirect_stderr, redirect_stdout

# 添加工项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_worker_initialization():
    """测试 Worker 类初始化"""
    print("=" * 70)
    print("测试 Worker 类初始化")
    print("=" * 70)
    
    # 捕获日志输出
    log_capture_string = io.StringIO()
    ch = logging.StreamHandler(log_capture_string)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    
    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.addHandler(ch)
    
    try:
        print("\n[1] 正在初始化 Worker 类...")
        from worker.main import Worker
        
        # 创建 Worker 实例
        worker = Worker()
        print("✓ Worker 实例化成功！")
        
        print("\n[2] 验证核心组件是否创建...")
        
        # 验证调度器
        has_scheduler = hasattr(worker, 'scheduler')
        print(f"  - TaskScheduler: {'✓ 已创建' if has_scheduler else '✗ 未创建'}")
        
        # 验证交易日缓存
        has_trade_day_cache = hasattr(worker, 'trade_day_cache')
        print(f"  - TradeDayCache: {'✓ 已创建' if has_trade_day_cache else '✗ 未创建'}")
        
        # 验证 gRPC 客户端（可能为 None）
        has_grpc_client = hasattr(worker, 'grpc_client')
        grpc_client_status = '✓ 已创建' if (has_grpc_client and worker.grpc_client is not None) else '⚠ 未连接（正常，Master 未运行）'
        print(f"  - gRPC Client: {grpc_client_status}")
        
        print("\n[3] 检查任务类型注册...")
        task_factory = worker.scheduler._task_factory
        expected_tasks = ["log_collector", "metric_converter", "database_collector", "kafka_collector"]
        for task_type in expected_tasks:
            status = '✓' if task_type in task_factory else '✗'
            print(f"  - {task_type}: {status} 已注册")
        
        all_tasks_registered = all(task in task_factory for task in expected_tasks)
        
        # 获取并打印捕获的日志
        print("\n[4] 初始化日志输出:")
        print("-" * 70)
        log_contents = log_capture_string.getvalue()
        print(log_contents if log_contents else "  (无日志输出)")
        
        # 验证关键日志信息
        print("\n[5] 验证关键日志...")
        required_logs = [
            "Initializing worker...",
            "TaskScheduler created",
            "TradeDayCache initialized",
            "Task types registered with scheduler factory",
            "Process monitor started",
            "Worker initialized successfully"
        ]
        
        all_logs_found = True
        for log_msg in required_logs:
            found = log_msg in log_contents
            all_logs_found = all_logs_found and found
            print(f"  - '{log_msg}': {'✓' if found else '✗'}")
        
        # 总结
        print("\n" + "=" * 70)
        success = has_scheduler and has_trade_day_cache and all_tasks_registered and all_logs_found
        
        if success:
            print("✓ 测试通过！Worker 初始化成功")
        else:
            print("✗ 测试失败！部分组件或功能未正常初始化")
        
        print("=" * 70)
        
        return success
        
    except Exception as e:
        print(f"\n✗ 测试失败: {type(e).__name__}: {e}")
        import traceback
        print("\n详细错误信息:")
        print(traceback.format_exc())
        return False
    finally:
        # 清理日志处理器
        root_logger.removeHandler(ch)


if __name__ == "__main__":
    success = test_worker_initialization()
    sys.exit(0 if success else 1)
