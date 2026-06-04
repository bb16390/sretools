from datetime import date, datetime
import threading
import logging
import asyncio
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
        self._fetch_event = threading.Event()
        self._response_received = False

        # 注册WebSocket消息处理器
        self._central_client.register_message_handler(
            "trade_day_data", self._handle_trade_day_data
        )

        # 立即获取交易日期
        self.fetch_trade_days()

        # 启动刷新定时器
        self.start_refresh_timer()

    def _handle_trade_day_data(self, data):
        """
        处理来自服务器的交易日数据响应
        """
        try:
            trade_days_list = data.get("trade_days", [])
            self._update_trade_days(trade_days_list)
        finally:
            self._response_received = True
            self._fetch_event.set()

    def fetch_trade_days(self):
        """
        从服务器获取未来一年的交易日
        """
        try:
            logger.info("开始获取交易日数据...")

            # 重置事件状态
            self._response_received = False
            self._fetch_event.clear()

            # 通过WebSocket发送查询请求
            asyncio.run(
                self._central_client.send_websocket_message({
                    "type": "trade_day_query",
                    "range": "future_1year"
                })
            )

            # 等待响应，最多等待10秒
            if not self._fetch_event.wait(timeout=10):
                logger.warning("获取交易日数据超时，将保留现有缓存")

        except Exception as e:
            logger.warning(f"获取交易日数据失败: {e}, 将保留现有缓存")

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

    def _update_trade_days(self, trade_days_list: list):
        """
        更新交易日缓存（内部方法，解析字符串日期）
        """
        try:
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
                self.fetch_trade_days()

        refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
        refresh_thread.start()
        logger.info(f"交易日刷新定时器已启动，刷新间隔: {self._refresh_interval} 秒")
