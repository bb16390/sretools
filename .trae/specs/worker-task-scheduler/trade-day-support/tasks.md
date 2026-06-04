# Tasks

- [x] Task 1: 创建 `TradeDayCache` 交易日缓存管理器
  - [x] 创建 `worker/scheduler/trade_day_cache.py`
  - [x] 实现 `TradeDayCache` 类，包含 `trade_days: set[date]` 缓存
  - [x] 实现 `fetch_trade_days()` 方法，通过 CentralClient 请求服务端未来1年交易日数据
  - [x] 实现 `is_trade_day(date)` 方法，判断指定日期是否为交易日
  - [x] 实现 `start_refresh_timer()` 方法，启动7200秒定时刷新任务
  - [x] 实现降级处理：服务端不可用时保留旧缓存，无缓存时默认所有日期为交易日

- [x] Task 2: 扩展 DatabaseCollectorTask，支持交易日配置
  - [x] 修改 `database_collector_task.py`，新增 `trade_day_only: bool` 配置字段（默认 false）
  - [x] 在 `_should_execute()` 触发判断中，集成 TradeDayCache 校验
  - [x] 当 `trade_day_only: true` 且当前为非交易日时，跳过执行并记录日志
  - [x] cron 表达式解析保持标准格式，不扩展语法

- [x] Task 3: 在 Worker 启动时初始化 TradeDayCache
  - [x] 在 `worker/main.py` 的 Worker 初始化流程中创建 TradeDayCache 实例
  - [x] 将 TradeDayCache 注入到 TaskScheduler
  - [x] 确保 TaskScheduler 持有 TradeDayCache 引用，传递给 DatabaseCollectorTask

- [x] Task 4: 实现交易日数据 WebSocket 消息处理
  - [x] 在 CentralClient 中添加 `trade_day_query` 消息类型处理
  - [x] 实现 `_handle_trade_day_data()` 方法，接收并解析服务端响应
  - [x] 将响应数据传递给 TradeDayCache 更新

- [x] Task 5: 添加单元测试
  - [x] 为 `TradeDayCache.is_trade_day()` 编写测试
  - [x] 为交易日跳过逻辑编写集成测试

# Task Dependencies
- Task 2 依赖 Task 1（需要 TradeDayCache 判断是否交易日）
- Task 3 依赖 Task 1
- Task 4 独立于 Task 1、2、3，可并行开发
- Task 5 依赖 Task 1、2
- Task 2 和 Task 4 可并行开发
