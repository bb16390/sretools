import unittest
from datetime import date
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from worker.scheduler.trade_day_cache import TradeDayCache


class TestTradeDayCache(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.mock_central_client = Mock()
        self.mock_central_client.register_message_handler = Mock()
        
    def test_is_trade_day_with_valid_cache(self):
        """测试 is_trade_day 方法在缓存有效时正确返回"""
        with patch.object(TradeDayCache, 'fetch_trade_days'):
            with patch.object(TradeDayCache, 'start_refresh_timer'):
                cache = TradeDayCache(self.mock_central_client)
                # 直接设置缓存
                cache.trade_days = {date(2025, 1, 2), date(2025, 1, 3)}
                
                self.assertTrue(cache.is_trade_day(date(2025, 1, 2)))
                self.assertFalse(cache.is_trade_day(date(2025, 1, 6)))  # Not in cache
                self.assertFalse(cache.is_trade_day(date(2025, 1, 4)))  # Weekend not in cache
    
    def test_is_trade_day_with_empty_cache(self):
        """测试 is_trade_day 方法在缓存为空时返回 True 并记录警告"""
        with patch.object(TradeDayCache, 'fetch_trade_days'):
            with patch.object(TradeDayCache, 'start_refresh_timer'):
                cache = TradeDayCache(self.mock_central_client)
                cache.trade_days = set()  # Empty cache
                
                with self.assertLogs('worker.scheduler.trade_day_cache', level='WARNING') as log:
                    result = cache.is_trade_day(date(2025, 1, 2))
                    self.assertTrue(result)
                    self.assertTrue(any("为空" in msg for msg in log.output))
    
    def test_update_trade_days_with_date_objects(self):
        """测试 update_trade_days 方法接受 date 对象列表"""
        with patch.object(TradeDayCache, 'fetch_trade_days'):
            with patch.object(TradeDayCache, 'start_refresh_timer'):
                cache = TradeDayCache(self.mock_central_client)
                dates = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
                
                cache.update_trade_days(dates)
                
                self.assertEqual(len(cache.trade_days), 3)
                self.assertIn(date(2025, 1, 2), cache.trade_days)
                self.assertIn(date(2025, 1, 3), cache.trade_days)
                self.assertIn(date(2025, 1, 6), cache.trade_days)


class TestTradeDayCacheInternalParsing(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.mock_central_client = Mock()
        self.mock_central_client.register_message_handler = Mock()
        
    def test_update_trade_days_from_strings(self):
        """测试内部方法 _update_trade_days 解析字符串日期"""
        with patch.object(TradeDayCache, 'fetch_trade_days'):
            with patch.object(TradeDayCache, 'start_refresh_timer'):
                cache = TradeDayCache(self.mock_central_client)
                date_strings = ["2025-01-02", "2025-01-03", "2025-01-06"]
                
                cache._update_trade_days(date_strings)
                
                self.assertEqual(len(cache.trade_days), 3)
                self.assertIn(date(2025, 1, 2), cache.trade_days)


if __name__ == '__main__':
    unittest.main()
