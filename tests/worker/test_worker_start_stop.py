#!/usr/bin/env python3
"""测试 Worker 的启动和停止功能"""

import sys
import os
import time
import threading
import logging
import io
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_worker_start_stop():
    """测试 Worker 启动和停止"""
    print("=" * 70)
    print("测试 Worker 启动和停止")
    print("=" * 70)
    
    log_capture_string = io.StringIO()
    ch = logging.StreamHandler(log_capture_string)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.addHandler(ch)
    
    worker = None
    success = False
    
    try:
        print("\n[1] 正在初始化 Worker 类...")
        from worker.main import Worker
        
        worker = Worker()
        print("✓ Worker 实例化成功！")
        
        print("\n[2] 准备启动 Worker 的 run 方法...")
        print("  - Worker 将运行 5 秒后停止")
        
        worker_thread = None
        stop_event = threading.Event()
        
        def run_worker():
            try:
                worker.run()
            except Exception as e:
                print(f"  - Worker 线程异常: {e}")
                import traceback
                print(traceback.format_exc())
        
        worker_thread = threading.Thread(target=run_worker, daemon=True)
        
        print("\n[3] 启动 Worker...")
        start_time = time.time()
        worker_thread.start()
        print("✓ Worker 已启动")
        
        print("\n[4] 等待 5 秒...")
        time.sleep(5)
        
        print("\n[5] 正在停止 Worker...")
        
        if hasattr(worker, 'scheduler'):
            worker.scheduler.shutdown()
        
        if hasattr(worker, 'grpc_client') and worker.grpc_client is not None:
            worker.grpc_client.close()
        
        end_time = time.time()
        print(f"✓ Worker 已停止，运行时间: {end_time - start_time:.2f} 秒")
        
        print("\n[6] 检查运行日志...")
        print("-" * 70)
        log_contents = log_capture_string.getvalue()
        print(log_contents if log_contents else "  (无日志输出)")
        
        print("\n[7] 验证关键事件...")
        required_events = [
            "Initializing worker...",
            "Worker initialized successfully",
            "Starting worker..."
        ]
        
        all_events_found = True
        for event in required_events:
            found = event in log_contents
            all_events_found = all_events_found and found
            print(f"  - '{event}': {'✓' if found else '✗'}")
        
        print("\n" + "=" * 70)
        success = all_events_found
        
        if success:
            print("✓ 测试通过！Worker 启动和停止正常")
        else:
            print("✗ 测试失败！部分关键事件未记录")
        
        print("=" * 70)
        
        return success
        
    except Exception as e:
        print(f"\n✗ 测试失败: {type(e).__name__}: {e}")
        import traceback
        print("\n详细错误信息:")
        print(traceback.format_exc())
        return False
    finally:
        root_logger.removeHandler(ch)


if __name__ == "__main__":
    success = test_worker_start_stop()
    sys.exit(0 if success else 1)
