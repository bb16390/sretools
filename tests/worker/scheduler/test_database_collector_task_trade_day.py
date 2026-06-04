import unittest
from datetime import date, datetime
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from worker.scheduler.tasks.database_collector_task import DatabaseCollectorTask


class TestDatabaseCollectorTaskTradeDay(unittest.TestCase):
    def test_trade_day_only_config_false_by_default(self):
        """测试 trade_day_only 默认为 False"""
        config = {
            "cron_expression": "0 9 * * *",
            "adapter_type": "sql",
            "adapter_config": {},
            "query": "SELECT 1"
        }
        
        task = DatabaseCollectorTask(
            task_type="database_collector",
            config=config,
            trade_day_cache=None
        )
        
        self.assertFalse(task.config.get("trade_day_only", False))
    
    def test_trade_day_only_config_true(self):
        """测试 trade_day_only 配置为 True"""
        config = {
            "cron_expression": "0 9 * * *",
            "adapter_type": "sql",
            "adapter_config": {},
            "query": "SELECT 1",
            "trade_day_only": True
        }
        
        task = DatabaseCollectorTask(
            task_type="database_collector",
            config=config,
            trade_day_cache=None
        )
        
        self.assertTrue(task.config.get("trade_day_only"))
    
    def test_trade_day_cache_passed_to_task(self):
        """测试 trade_day_cache 被正确传递到任务"""
        mock_cache = Mock()
        config = {
            "cron_expression": "0 9 * * *",
            "adapter_type": "sql",
            "adapter_config": {},
            "query": "SELECT 1"
        }
        
        task = DatabaseCollectorTask(
            task_type="database_collector",
            config=config,
            trade_day_cache=mock_cache
        )
        
        self.assertEqual(task._trade_day_cache, mock_cache)


if __name__ == '__main__':
    unittest.main()
