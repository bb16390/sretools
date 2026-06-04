import pytest
from datetime import date, datetime
from unittest.mock import Mock
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from worker.scheduler.tasks.database_collector_task import DatabaseCollectorTask


def test_trade_day_only_config_false_by_default():
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
    
    assert task.config.get("trade_day_only", False) is False


def test_trade_day_only_config_true():
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
    
    assert task.config.get("trade_day_only") is True


def test_trade_day_cache_passed_to_task():
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
    
    assert task._trade_day_cache == mock_cache