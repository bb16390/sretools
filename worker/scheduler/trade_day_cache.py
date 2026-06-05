from datetime import date, datetime
import threading
import logging
import time

logger = logging.getLogger(__name__)


class TradeDayCache:
    """
    股票交易日缓存管理器
    """

    def __init__(self, central_client):
        self.trade_days: set[date] = set()
        self._central_client = central_client
        self._refresh_interval = 7200  # 秒
        self._last_fetch_time: datetime = None

        # 立即获取交易日期
        # For now, we'll initialize empty - master will push updates
        logger.info("TradeDayCache initialized")

        # 启动刷新定时器
        self.start_refresh_timer()

    def update_trade_days(self, dates: list):
        """
        更新交易日缓存（公共方法，供外部调用）
        dates: date 对象列表
        """
        try:
            new_trade_days = set(dates)
            self.trade_days = new_trade_days
            self._last_fetch_time = datetime.now()
            logger.info(f"交易日缓存已更新，共 {len(self.trade_days)} 个交易日")
        except Exception as e:
            logger.error(f"更新交易日数据失败: {e}")

    def update_trade_days_from_data(self, data):
        """
        更新交易日缓存（从 gRPC 数据）
        """
        try:
            trade_days_list = data.get("trade_days", [])
            new_trade_days = set()
            for day_str in trade_days_list:
                new_trade_days.add(date.fromisoformat(day_str))

            self.trade_days = new_trade_days
            self._last_fetch_time = datetime.now()
            logger.info(f"交易日缓存已更新，共 {len(self.trade_days)} 个交易日")

        except Exception as e:
            logger.error(f"解析交易日数据失败: {e}")

    def is_trade_day(self, target_date: date) -> bool:
        """
        判断指定日期是否为交易日

        如果缓存为空，返回True并记录警告日志
        """
        if not self.trade_days:
            logger.warning("交易日缓存为空，无法判断日期有效性，默认返回True")
            return True

        return target_date in self.trade_days

    def start_refresh_timer(self):
        """
        启动定时刷新线程，每7200秒刷新一次交易日数据
        """
        def refresh_loop():
            while True:
                threading.Event().wait(self._refresh_interval)
                # For now, just log - master pushes updates
                logger.debug("TradeDayCache refresh timer tick")

        refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
        refresh_thread.start()
        logger.info(f"交易日刷新定时器已启动，刷新间隔: {self._refresh_interval} 秒")
