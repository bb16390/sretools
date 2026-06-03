import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from logging import FileHandler
from dashboard.core.logging import AsyncFileHandler
import tempfile


def test_async_file_handler_single_process_multi_thread():
    """测试单进程多线程下的性能"""
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # 配置日志
        file_handler = FileHandler(temp_path)
        async_handler = AsyncFileHandler(file_handler)
        logger = logging.getLogger('test_single_process')
        logger.setLevel(logging.INFO)
        logger.addHandler(async_handler)
        
        # 测试参数
        num_threads = 10
        num_logs_per_thread = 1000
        
        # 开始时间
        start_time = time.time()
        
        # 多线程写入日志
        def write_logs(thread_id):
            for i in range(num_logs_per_thread):
                logger.info(f"Thread {thread_id} log {i}")
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            executor.map(write_logs, range(num_threads))
        
        # 关闭处理器
        async_handler.close()
        
        # 结束时间
        end_time = time.time()
        total_time = end_time - start_time
        total_logs = num_threads * num_logs_per_thread
        
        # 验证日志文件
        with open(temp_path, 'r') as f:
            log_count = len(f.readlines())
        
        print(f"单进程多线程测试: {total_logs} 条日志, 耗时 {total_time:.2f} 秒, QPS: {total_logs / total_time:.2f}")
        assert log_count > 0, "没有日志写入"
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)


def worker_function(num_logs, temp_path):
    """多进程测试的工作函数"""
    # 配置日志
    file_handler = FileHandler(temp_path)
    async_handler = AsyncFileHandler(file_handler)
    logger = logging.getLogger(f'worker_{os.getpid()}')
    logger.setLevel(logging.INFO)
    logger.addHandler(async_handler)
    
    # 多线程写入日志
    num_threads = 5
    num_logs_per_thread = num_logs // num_threads
    
    def write_logs(thread_id):
        for i in range(num_logs_per_thread):
            logger.info(f"Process {os.getpid()} Thread {thread_id} log {i}")
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        executor.map(write_logs, range(num_threads))
    
    # 关闭处理器
    async_handler.close()


def test_async_file_handler_multi_process_multi_thread():
    """测试多进程多线程下的性能"""
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # 测试参数
        num_processes = 4
        num_logs_per_process = 5000
        
        # 开始时间
        start_time = time.time()
        
        # 多进程测试
        with ProcessPoolExecutor(max_workers=num_processes) as executor:
            executor.map(worker_function, [num_logs_per_process] * num_processes, [temp_path] * num_processes)
        
        # 结束时间
        end_time = time.time()
        total_time = end_time - start_time
        total_logs = num_processes * num_logs_per_process
        
        # 验证日志文件
        with open(temp_path, 'r') as f:
            log_count = len(f.readlines())
        
        print(f"多进程多线程测试: {total_logs} 条日志, 耗时 {total_time:.2f} 秒, QPS: {total_logs / total_time:.2f}")
        assert log_count > 0, "没有日志写入"
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    test_async_file_handler_single_process_multi_thread()
    test_async_file_handler_multi_process_multi_thread()
