import pytest
from datetime import date
from unittest.mock import Mock, patch
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from worker.scheduler.trade_day_cache import TradeDayCache


@pytest.fixture
def mock_central_client():
    client = Mock()
    client.register_message_handler = Mock()
    return client


@pytest.fixture
def trade_day_cache(mock_central_client):
    with patch.object(TradeDayCache, 'fetch_trade_days'):
        with patch.object(TradeDayCache, 'start_refresh_timer'):
            cache = TradeDayCache(mock_central_client)
            yield cache


def test_is_trade_day_with_valid_cache(trade_day_cache):
    """测试 is_trade_day 方法在缓存有效时正确返回"""
    trade_day_cache.trade_days = {date(2025, 1, 2), date(2025, 1, 3)}
    
    assert trade_day_cache.is_trade_day(date(2025, 1, 2)) is True
    assert trade_day_cache.is_trade_day(date(2025, 1, 6)) is False  # Not in cache
    assert trade_day_cache.is_trade_day(date(2025, 1, 4)) is False  # Weekend not in cache


def test_is_trade_day_with_empty_cache(trade_day_cache, caplog):
    """测试 is_trade_day 方法在缓存为空时返回 True 并记录警告"""
    trade_day_cache.trade_days = set()  # Empty cache
    
    result = trade_day_cache.is_trade_day(date(2025, 1, 2))
    
    assert result is True
    assert any("为空" in record.message for record in caplog.records)


def test_update_trade_days_with_date_objects(trade_day_cache):
    """测试 update_trade_days 方法接受 date 对象列表"""
    dates = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
    
    trade_day_cache.update_trade_days(dates)
    
    assert len(trade_day_cache.trade_days) == 3
    assert date(2025, 1, 2) in trade_day_cache.trade_days
    assert date(2025, 1, 3) in trade_day_cache.trade_days
    assert date(2025, 1, 6) in trade_day_cache.trade_days


def test_update_trade_days_from_strings(mock_central_client):
    """测试内部方法 _update_trade_days 解析字符串日期"""
    with patch.object(TradeDayCache, 'fetch_trade_days'):
        with patch.object(TradeDayCache, 'start_refresh_timer'):
            cache = TradeDayCache(mock_central_client)
            date_strings = ["2025-01-02", "2025-01-03", "2025-01-06"]
            
            cache._update_trade_days(date_strings)
            
            assert len(cache.trade_days) == 3
            assert date(2025, 1, 2) in cache.trade_days