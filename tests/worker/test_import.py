#!/usr/bin/env python3
"""测试 worker.main 模块的导入"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_import_worker_main():
    """测试导入 worker.main 模块"""
    print("正在测试导入 worker.main 模块...")
    
    try:
        import worker.main
        print("✓ worker.main 模块导入成功！")
        
        print("\nworker.main 模块的内容:")
        print(f"  导入的模块: {dir(worker.main)}")
        print(f"  Worker 类: {hasattr(worker.main, 'Worker')}")
        
        return True
    except Exception as e:
        print(f"✗ worker.main 模块导入失败: {type(e).__name__}: {e}")
        import traceback
        print("\n详细错误信息:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_import_worker_main()
    sys.exit(0 if success else 1)
