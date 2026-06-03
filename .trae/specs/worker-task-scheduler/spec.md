# Worker 任务调度管理器 Spec

## Why
当前 Worker 端缺乏统一的任务调度与管理机制。LogCollector、MetricConverter 等模块各自独立运行，无法按需启停，也无法向 Master 统一上报任务执行状态和性能数据。需要新增一个任务调度管理器，统一管理实时日志采集、日志转指标、定时数据库采集三类任务，支持任务启停和状态上报。

## What Changes
- 新增 `worker/scheduler/` 模块，包含任务调度管理器核心实现
- 新增任务抽象基类，统一任务生命周期（启动、停止、暂停、恢复）
- 实现实时日志采集任务（封装现有 LogCollector）
- 实现日志转指标任务（封装现有 MetricConverter）
- 实现定时数据库采集任务（利用现有 Adapter 体系按 cron 表达式定时执行 SQL 查询）
- 通过 WebSocket 向 Master 上报任务状态（执行结果、耗时等）
- 将现有 Worker 主循环改为由 TaskScheduler 驱动

## Impact
- Affected specs: 无（新增能力）
- Affected code: `worker/main.py`（改用调度器启动）、`worker/communicator/central_client.py`（利用现有 WebSocket 通道上报状态）、新增 `worker/scheduler/` 整个模块

## ADDED Requirements

### Requirement: 任务抽象基类
系统 SHALL 提供 `BaseTask` 抽象基类，定义统一的任务生命周期接口：`start()`、`stop()`、`pause()`、`resume()`，以及任务状态存储和任务配置。

#### Scenario: 任务正常启停
- **WHEN** 调度器调用任务的 `start()` 方法
- **THEN** 任务进入 RUNNING 状态并执行核心逻辑
- **WHEN** 调度器调用任务的 `stop()` 方法
- **THEN** 任务进入 STOPPED 状态并释放资源

#### Scenario: 任务暂停与恢复
- **WHEN** 调度器调用任务的 `pause()` 方法
- **THEN** 任务进入 PAUSED 状态并暂停核心逻辑
- **WHEN** 调度器调用任务的 `resume()` 方法
- **THEN** 任务恢复为 RUNNING 状态并继续执行

### Requirement: 实时日志采集任务
系统 SHALL 提供 `LogCollectorTask`，封装现有 `LogCollector` 为可被调度器管理的任务，支持按配置的参数（采集间隔、批量大小等）实时采集日志。

#### Scenario: 发起日志采集任务
- **WHEN** 调度器收到发起日志采集任务的指令
- **THEN** 创建 LogCollectorTask 实例并启动，持续从日志源采集日志数据

#### Scenario: 停止日志采集任务
- **WHEN** 调度器收到停止日志采集任务的指令
- **THEN** LogCollectorTask 停止采集线程，清理队列中的残留数据

### Requirement: 日志转指标任务
系统 SHALL 提供 `MetricConverterTask`，封装现有 `MetricConverter` 为可被调度器管理的任务，支持将已采集的日志按规则转换为时序指标。

#### Scenario: 发起日志转指标任务
- **WHEN** 调度器收到发起日志转指标任务的指令
- **THEN** 创建 MetricConverterTask 实例并启动，持续将日志转换为指标数据

#### Scenario: 停止日志转指标任务
- **WHEN** 调度器收到停止日志转指标任务的指令
- **THEN** MetricConverterTask 停止转换线程，发送剩余指标队列数据

### Requirement: 定时数据库采集任务
系统 SHALL 提供 `DatabaseCollectorTask`，支持按 cron 表达式定时连接目标数据库、执行配置的 SQL 查询并返回结果。

#### Scenario: 按 cron 表达式定时执行
- **WHEN** 配置了 cron 表达式为 `0 */5 * * *`（每5分钟）的数据库采集任务启动
- **THEN** 系统每5分钟通过指定 Adapter 连接数据库执行 SQL 查询，获取采集结果

#### Scenario: 停止定时采集任务
- **WHEN** 调度器收到停止数据库采集任务的指令
- **THEN** DatabaseCollectorTask 取消下次定时触发，完成当前执行中的查询后停止

### Requirement: 任务调度管理器
系统 SHALL 提供 `TaskScheduler` 作为 Worker 端任务调度核心，负责管理所有任务的生命周期、接收 Master 指令、上报任务状态。

#### Scenario: 注册与管理任务
- **WHEN** Master 通过 WebSocket 下发任务创建指令
- **THEN** TaskScheduler 根据任务类型创建对应任务实例、启动任务、并注册到内部管理表
- **WHEN** Master 下发任务停止指令
- **THEN** TaskScheduler 查找对应任务并调用其 `stop()` 方法

#### Scenario: 根据任务 ID 启停
- **WHEN** 指令中指定了具体 task_id
- **THEN** TaskScheduler 仅操作该特定任务实例，不影响其他运行中的任务

### Requirement: 任务状态上报
系统 SHALL 在每个任务执行完成后（或按固定间隔）通过 WebSocket 向 Master 上报任务状态，包含任务 ID、任务类型、执行状态、执行结果、执行耗时等字段。

#### Scenario: 单次执行完成上报
- **WHEN** 一个数据库采集任务执行完成（成功或失败）
- **THEN** 通过 CentralClient 的 WebSocket 通道上报一条状态消息，包含 `task_id`、`status`（success/failed）、`result`、`duration_ms`、`timestamp`

#### Scenario: 持续运行任务定期上报
- **WHEN** 实时日志采集任务运行中
- **THEN** 按配置的间隔（默认30秒）上报一次运行状态，包含 `task_id`、`status`（running）、`metrics`（如已采集日志数量、队列大小）、`timestamp`

#### Scenario: 上报消息格式
- **WHEN** 任上报触发
- **THEN** 上报消息 SHALL 为 JSON 格式，至少包含以下字段：
  - `type`: "task_status"
  - `worker_id`: Worker 标识
  - `task_id`: 任务唯一标识
  - `task_type`: 任务类型（log_collector / metric_converter / database_collector）
  - `status`: 任务状态（running / paused / stopped / success / failed）
  - `result`: 任务执行结果（成功时的输出摘要或失败时的错误信息）
  - `duration_ms`: 执行耗时（毫秒）
  - `timestamp`: 上报时间戳
  - `extra`: 扩展字段（可选，承载任务特定指标数据）

### Requirement: 通过 WebSocket 接收 Master 调度指令
系统 SHALL 扩展 CentralClient 的消息处理能力，解析 Master 下发的任务调度指令并转发给 TaskScheduler 处理。

#### Scenario: 接收任务创建指令
- **WHEN** Master 通过 WebSocket 发送 `{"type": "task_create", "task_type": "database_collector", "config": {...}}`
- **THEN** CentralClient 解析消息后调用 TaskScheduler 创建并启动对应任务

#### Scenario: 接收任务停止指令
- **WHEN** Master 通过 WebSocket 发送 `{"type": "task_stop", "task_id": "xxx"}`
- **THEN** CentralClient 解析消息后调用 TaskScheduler 停止指定任务