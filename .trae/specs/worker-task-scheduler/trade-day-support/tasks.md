# Tasks

- [ ] Task 1: 创建 `TradeDayCache` 交易日缓存管理器
  - [ ] 创建 `worker/scheduler/trade_day_cache.py`
  - [ ] 实现 `TradeDayCache` 类，包含 `trade_days: set[date]` 缓存
  - [ ] 实现 `fetch_trade_days()` 方法，通过 CentralClient 请求服务端未来1年交易日数据
  - [ ] 实现 `is_trade_day(date)` 方法，判断指定日期是否为交易日
  - [ ] 实现 `start_refresh_timer()` 方法，启动7200秒定时刷新任务
  - [ ] 实现降级处理：服务端不可用时保留旧缓存，无缓存时默认所有日期为交易日

- [ ] Task 2: 扩展 cron 表达式解析器，支持 T/F 标记
  - [ ] 创建 `worker/scheduler/cron_parser.py`，扩展 `CronParser` 类
  - [ ] 扩展 `_parse_weekday_field()` 方法，解析 `T`（交易日）和 `F`（非交易日）标记
  - [ ] 支持复合格式如 `1-5:T`、`*:T`、`*:F`
  - [ ] 实现 `should_run_on_date(cron_expr, date)` 方法，返回是否应在指定日期执行
  - [ ] 保持对标准 cron 格式的向后兼容

- [ ] Task 3: 扩展 DatabaseCollectorTask，支持交易日配置
  - [ ] 修改 `database_collector_task.py`，新增 `trade_day_only: bool` 配置字段
  - [ ] 在 `_should_execute()` 触发判断中，集成 TradeDayCache 校验
  - [ ] 当 `trade_day_only: true` 且当前为非交易日时，跳过执行并记录日志
  - [ ] 默认 `trade_day_only: false`

- [ ] Task 4: 在 Worker 启动时初始化 TradeDayCache
  - [ ] 在 `worker/main.py` 的 Worker 初始化流程中创建 TradeDayCache 实例
  - [ ] 将 TradeDayCache 注入到 TaskScheduler
  - [ ] 确保 TaskScheduler 持有 TradeDayCache 引用，传递给 DatabaseCollectorTask

- [ ] Task 5: 实现交易日数据 WebSocket 消息处理
  - [ ] 在 CentralClient 中添加 `trade_day_query` 消息类型处理
  - [ ] 实现 `_handle_trade_day_query()` 方法，接收并解析服务端响应
  - [ ] 将响应数据传递给 TradeDayCache 更新

- [ ] Task 6: 添加单元测试
  - [ ] 为 `TradeDayCache.is_trade_day()` 编写测试
  - [ ] 为 `CronParser` 的 T/F 标记解析编写测试
  - [ ] 为交易日跳过逻辑编写集成测试

# Task Dependencies
- Task 2 依赖 Task 1（需要 TradeDayCache 判断是否交易日）
- Task 3 依赖 Task 1 和 Task 2
- Task 4 依赖 Task 1
- Task 5 独立
- Task 6 依赖 Task 1、2、3
- Task 2 和 Task 5 可并行开发
