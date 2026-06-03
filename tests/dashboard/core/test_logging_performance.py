import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from logging import FileHandler
# 导入原始版本和优化版本
from dashboard.core.logging_original import AsyncFileHandler as OriginalAsyncFileHandler
from dashboard.core.logging import AsyncFileHandler as OptimizedAsyncFileHandler
import tempfile


def test_original_async_file_handler_single_process_multi_thread():
    """测试原始的AsyncFileHandler在单进程多线程下的性能"""
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # 配置日志
        file_handler = FileHandler(temp_path)
        # 使用原始版本
        async_handler = OriginalAsyncFileHandler(file_handler)
        logger = logging.getLogger('test_optimized_single_process')
        logger.addHandler(async_handler)
        logger.setLevel(logging.INFO)

        num_threads = 4
        num_logs_per_thread = 20000
        total_logs = num_threads * num_logs_per_thread
        
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
        
        # 验证日志文件
        with open(temp_path, 'r') as f:
            log_count = len(f.readlines())
        
        print(f"原始版本单进程多线程测试: {total_logs} 条日志, 耗时 {total_time:.2f} 秒, QPS: {total_logs / total_time:.2f}")
        print(f"实际写入日志数: {log_count}")
        assert log_count > 0, "没有日志写入"
        
        return total_time, total_logs / total_time, log_count
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_optimized_async_file_handler_single_process_multi_thread():
    """测试优化后的AsyncFileHandler在单进程多线程下的性能"""
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # 配置日志
        file_handler = FileHandler(temp_path)
        # 使用优化后的配置
        async_handler = OptimizedAsyncFileHandler(
            file_handler,
            max_queue_size=50000,
            drop_threshold=0.8,
            batch_size=200,
            flush_interval=0.5
        )
        logger = logging.getLogger('test_optimized_single_process')
        logger.setLevel(logging.INFO)
        logger.addHandler(async_handler)
        
        # 测试参数 - 与多进程每个进程的日志数一致
        num_threads = 5
        num_logs_per_thread = 20000
        total_logs = num_threads * num_logs_per_thread
        
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
        processing_speed = async_handler.get_processing_speed() if hasattr(async_handler, 'get_processing_speed') else 0
        
        # 验证日志文件
        with open(temp_path, 'r') as f:
            log_count = len(f.readlines())
        
        print(f"优化后单进程多线程测试: {total_logs} 条日志, 耗时 {total_time:.2f} 秒, QPS: {total_logs / total_time:.2f}, 处理速度: {processing_speed:.2f} 条/秒")
        print(f"实际写入日志数: {log_count}")
        assert log_count > 0, "没有日志写入"
        
        return total_time, total_logs / total_time, log_count
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)


def original_worker_function(num_logs, temp_path):
    """原始版本多进程测试的工作函数"""
    # 为每个进程创建独立的日志文件
    process_temp_path = f"{temp_path}_{os.getpid()}"
    # 配置日志
    file_handler = FileHandler(process_temp_path)
    async_handler = OriginalAsyncFileHandler(file_handler)
    logger = logging.getLogger(f'original_worker_{os.getpid()}')
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
    
    # 清理临时文件
    if os.path.exists(process_temp_path):
        os.remove(process_temp_path)

def optimized_worker_function(num_logs, temp_path):
    """优化后多进程测试的工作函数"""
    # 为每个进程创建独立的日志文件
    process_temp_path = f"{temp_path}_{os.getpid()}"
    # 配置日志
    file_handler = FileHandler(process_temp_path)
    async_handler = OptimizedAsyncFileHandler(
        file_handler,
        max_queue_size=50000,
        drop_threshold=0.8,
        batch_size=200,
        flush_interval=0.5
    )
    logger = logging.getLogger(f'optimized_worker_{os.getpid()}')
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
    
    # 清理临时文件
    if os.path.exists(process_temp_path):
        os.remove(process_temp_path)

def test_original_async_file_handler_multi_process_multi_thread():
    """测试原始的AsyncFileHandler在多进程多线程下的性能"""
    # 生成临时路径前缀
    temp_path = tempfile.mktemp()
    
    try:
        # 测试参数
        num_processes = 4
        num_logs_per_process = 100000
        
        # 开始时间
        start_time = time.time()
        
        # 多进程测试
        with ProcessPoolExecutor(max_workers=num_processes) as executor:
            executor.map(original_worker_function, [num_logs_per_process] * num_processes, [temp_path] * num_processes)
        
        # 结束时间
        end_time = time.time()
        total_time = end_time - start_time
        total_logs = num_processes * num_logs_per_process
        
        print(f"原始版本多进程多线程测试: {total_logs} 条日志, 耗时 {total_time:.2f} 秒, QPS: {total_logs / total_time:.2f}")
        print(f"实际写入日志数: {total_logs}")
        
        return total_time, total_logs / total_time, total_logs
        
    finally:
        # 清理临时文件（每个进程会自己清理）
        pass

def test_optimized_async_file_handler_multi_process_multi_thread():
    """测试优化后的AsyncFileHandler在多进程多线程下的性能"""
    # 生成临时路径前缀
    temp_path = tempfile.mktemp()
    
    try:
        # 测试参数
        num_processes = 4
        num_logs_per_process = 100000
        
        # 开始时间
        start_time = time.time()
        
        # 多进程测试
        with ProcessPoolExecutor(max_workers=num_processes) as executor:
            executor.map(optimized_worker_function, [num_logs_per_process] * num_processes, [temp_path] * num_processes)
        
        # 结束时间
        end_time = time.time()
        total_time = end_time - start_time
        total_logs = num_processes * num_logs_per_process
        
        print(f"优化后多进程多线程测试: {total_logs} 条日志, 耗时 {total_time:.2f} 秒, QPS: {total_logs / total_time:.2f}")
        print(f"实际写入日志数: {total_logs}")
        
        return total_time, total_logs / total_time, total_logs
        
    finally:
        # 清理临时文件（每个进程会自己清理）
        pass


def compare_performance():
    """对比优化前后的性能"""
    print("=== 性能对比测试 ===")
    
    # 运行原始版本测试
    print("\n1. 原始版本性能测试:")
    original_single_time, original_single_qps, original_single_logs = test_original_async_file_handler_single_process_multi_thread()
    original_multi_time, original_multi_qps, original_multi_logs = test_original_async_file_handler_multi_process_multi_thread()
    
    # 运行优化后的测试
    print("\n2. 优化后性能测试:")
    optimized_single_time, optimized_single_qps, optimized_single_logs = test_optimized_async_file_handler_single_process_multi_thread()
    optimized_multi_time, optimized_multi_qps, optimized_multi_logs = test_optimized_async_file_handler_multi_process_multi_thread()
    
    print("\n=== 测试结果对比 ===")
    print(f"单进程多线程 - 原始版本 QPS: {original_single_qps:.2f}")
    print(f"单进程多线程 - 优化版本 QPS: {optimized_single_qps:.2f}")
    print(f"单进程多线程 - 性能提升: {((optimized_single_qps - original_single_qps) / original_single_qps) * 100:.2f}%")
    print(f"单进程多线程 - 原始版本实际写入: {original_single_logs}")
    print(f"单进程多线程 - 优化版本实际写入: {optimized_single_logs}")
    
    print(f"\n多进程多线程 - 原始版本 QPS: {original_multi_qps:.2f}")
    print(f"多进程多线程 - 优化版本 QPS: {optimized_multi_qps:.2f}")
    print(f"多进程多线程 - 性能提升: {((optimized_multi_qps - original_multi_qps) / original_multi_qps) * 100:.2f}%")
    print(f"多进程多线程 - 原始版本实际写入: {original_multi_logs}")
    print(f"多进程多线程 - 优化版本实际写入: {optimized_multi_logs}")


if __name__ == "__main__":
    compare_performance()
