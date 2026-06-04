# Worker 任务调度器 - 股票交易日扩展 Spec

## Why
现有 Worker 定时任务基于标准 cron 表达式调度，但无法针对股票交易日进行判断。实际业务中，部分定时任务（如财报采集、行情数据处理）需要在股票交易日才执行，需要扩展 cron 解析能力，支持类似 `0 9 * * 1-5:T`（每周一至周五的交易日凌晨9点）这样的语法。

## What Changes
- 扩展 cron 表达式解析器，支持股票交易日标记 `T`（trade day）和 `F`（non-trade day）
- 新增交易日缓存管理器，从服务端拉取未来1年交易日数据，7200秒定时刷新
- 交易日数据通过 WebSocket 或 HTTP API 从 Master 服务端获取
- DatabaseCollectorTask 的 cron 配置新增 `trade_day_only` 布尔字段，控制是否仅在交易日执行

## Impact
- Affected specs: `worker-task-scheduler`（扩展现有定时任务调度能力）
- Affected code: `worker/scheduler/tasks/database_collector_task.py`（扩展 cron 解析）、新增 `worker/scheduler/trade_day_cache.py`（交易日缓存管理）

## ADDED Requirements

### Requirement: 交易日缓存管理器
系统 SHALL 提供 `TradeDayCache` 管理器，负责从服务端获取并缓存股票交易日数据。

#### Scenario: 初始化时拉取交易日数据
- **WHEN** Worker 启动并初始化 TradeDayCache
- **THEN** 向服务端请求未来1年的所有股票交易日日期列表
- **THEN** 将数据缓存到内存，并启动7200秒定时刷新任务

#### Scenario: 定时刷新交易日数据
- **WHEN** 距离上次拉取已过7200秒
- **THEN** 再次向服务端请求最新交易日数据
- **THEN** 更新内存缓存

#### Scenario: 查询某日期是否为交易日
- **WHEN** 调用 `is_trade_day(date)` 方法
- **THEN** 返回该日期是否在缓存的交易日集合中

#### Scenario: 服务端不可用时的降级处理
- **WHEN** 无法连接到服务端获取交易日数据
- **THEN** 使用内存中已缓存的旧数据继续工作
- **WHEN** 既无网络又无缓存时
- **THEN** 记录警告日志，默认所有日期视为交易日

### Requirement: 扩展 cron 表达式解析
系统 SHALL 扩展现有 cron 解析逻辑，支持在星期字段使用 `T`（交易日的周一至周五）和 `F`（非交易日）标记。

#### Scenario: 解析 `0 9 * * 1-5:T` 格式（仅交易日的周一至周五）
- **WHEN** cron 表达式中星期字段为 `1-5:T`
- **THEN** `1-5` 表示周一至周五，`T` 标记表示这些天必须是交易日
- **WHEN** 当前时间为周一但非交易日
- **THEN** 该 cron 表达式不触发执行
- **WHEN** 当前时间为周一且为交易日
- **THEN** 该 cron 表达式在9:00触发执行

#### Scenario: 解析 `0 9 * * *:T` 格式（仅在交易日执行，不限制星期）
- **WHEN** cron 表达式中星期字段为 `*:T`
- **THEN** `*` 表示任意星期，`T` 标记要求必须是交易日
- **WHEN** 当前日期为交易日
- **THEN** 该 cron 表达式在9:00触发执行

#### Scenario: 解析 `0 9 * * *:F` 格式（非交易日执行）
- **WHEN** cron 表达式中星期字段为 `*:F`
- **THEN** `F` 标记表示必须是**非**交易日
- **WHEN** 当前日期为非交易日（如周末或 holiday）
- **THEN** 该 cron 表达式在9:00触发执行

#### Scenario: 标准 cron 表达式不受影响
- **WHEN** cron 表达式为标准格式，如 `0 9 * * 1-5`（无 T/F 标记）
- **THEN** 按标准周一定至周五9:00执行，不进行交易日校验

### Requirement: DatabaseCollectorTask 交易日配置
系统 SHALL 扩展 DatabaseCollectorTask 的配置，支持 `trade_day_only` 布尔字段。

#### Scenario: 配置 `trade_day_only: true`
- **WHEN** 数据库采集任务的 cron 表达式为 `0 9 * * 1-5`，且 `trade_day_only: true`
- **THEN** 系统仅在同时满足以下条件时执行：
  - 当前日期为股票交易日
  - 当前时间为9:00
  - 当前星期在1-5范围内

#### Scenario: 配置 `trade_day_only: false`（默认）
- **WHEN** 数据库采集任务的 `trade_day_only: false` 或未配置
- **THEN** 按标准 cron 表达式执行，不进行交易日校验

### Requirement: 交易日数据获取接口
系统 SHALL 通过 Worker 已有的 CentralClient 向服务端请求交易日数据。

#### Scenario: 通过 WebSocket 请求交易日数据
- **WHEN** TradeDayCache 需要刷新交易日数据
- **THEN** 通过 CentralClient 发送请求消息：`{"type": "trade_day_query", "range": "future_1year"}`
- **WHEN** 收到服务端响应 `{"type": "trade_day_data", "trade_days": ["2025-01-02", "2025-01-03", ...]}`
- **THEN** 解析并更新内存缓存

## MODIFIED Requirements

### Requirement: DatabaseCollectorTask cron 触发逻辑
在现有 cron 触发逻辑基础上，增加交易日判断：

#### Scenario: 触发前校验交易日
- **WHEN** croniter 计算的下次执行时间到达
- **THEN** 如果任务配置了 `trade_day_only: true`，先调用 `TradeDayCache.is_trade_day()` 校验
- **WHEN** 校验结果为非交易日
- **THEN** 跳过本次执行，重新计算并等待下次触发时间
