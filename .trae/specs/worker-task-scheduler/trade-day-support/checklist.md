# Checklist

- [x] TradeDayCache 类正确实现 `trade_days: set[date]` 缓存属性
- [x] `fetch_trade_days()` 通过 CentralClient 请求服务端数据，解析并更新缓存
- [x] `is_trade_day(date)` 正确判断指定日期是否在交易日集合中
- [x] `start_refresh_timer()` 启动7200秒定时刷新任务
- [x] 服务端不可用时降级使用旧缓存
- [x] 无网络且无缓存时默认所有日期为交易日，并记录警告日志
- [x] DatabaseCollectorTask 配置中正确处理 `trade_day_only` 字段
- [x] DatabaseCollectorTask 在 `trade_day_only: true` 时调用 TradeDayCache 校验
- [x] 非交易日时正确跳过执行并记录日志
- [x] cron 表达式解析保持标准格式（无 T/F 语法扩展）
- [x] Worker 启动时正确初始化 TradeDayCache
- [x] TradeDayCache 被正确注入到 TaskScheduler
- [x] CentralClient 支持 `trade_day_query` 消息类型
- [x] CentralClient 收到 `trade_day_data` 响应后正确更新 TradeDayCache
- [x] 为 TradeDayCache.is_trade_day() 编写了单元测试
- [x] 为交易日跳过逻辑编写了集成测试
