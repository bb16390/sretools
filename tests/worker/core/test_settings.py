import unittest
from worker.core.settings import settings


class TestSettings(unittest.TestCase):
    def test_settings_initialization(self):
        """测试配置初始化"""
        self.assertIsNotNone(settings)
        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 5501)
        self.assertTrue(settings.debug)
        self.assertIsNotNone(settings.worker_id)
    
    def test_central_servers(self):
        """测试中心端服务器配置"""
        self.assertIsInstance(settings.central_servers, list)
        self.assertGreater(len(settings.central_servers), 0)
    
    def test_log_configuration(self):
        """测试日志配置"""
        self.assertEqual(settings.log_level, "DEBUG")
        self.assertIsNotNone(settings.log_dir)
        self.assertIsNotNone(settings.error_log_dir)
    
    def test_collect_configuration(self):
        """测试收集配置"""
        self.assertEqual(settings.log_collect_interval, 5)
        self.assertEqual(settings.log_batch_size, 1000)
        self.assertEqual(settings.log_queue_size, 10000)


if __name__ == '__main__':
    unittest.main()
