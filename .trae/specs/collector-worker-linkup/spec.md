# Collector ↔ Worker 联动 Spec

## Why

当前 master 项目的 `apps/collector/` 模块已具备数据源、采集任务的前端管理能力（数据源选择、SQL 配置、预览、暂停/恢复按钮），`CollectorTask` 表也保留了 `job_id` / `worker_id` / `last_run_*` / `total_*` 等执行字段。但 master 与 worker 之间的 gRPC 双向流通道仅完成了 worker 端的指令接收与状态上报骨架，master 端既未向 worker 下发采集任务，也未消费 worker 上报的 `TaskStatus` 去回写 `CollectorTask` 字段，导致 collector 与 worker 实际未联动：
- 新建采集任务后无法落到任意 worker 执行
- 预览按钮当前仅返回源数据库列表，未真正试采，无法保证新增任务在保存前已可成功执行
- worker 端 `send_websocket_message` / `report_task_status` 为空实现，master 端 `Communicate` 收到 `task_status` 仅打印日志，`CollectorTask` 的执行统计字段始终为初始值

需要在不改动 master `apps/collector/` 现有前端配置（表单字段、模型字段、DataSource/CollectorTask 列表与详情页布局）的前提下，打通 collector 与 worker 的联动闭环。

## What Changes

- master 端：保留 `apps/collector/` 现有前端配置不动；新增后端逻辑实现：
  - 预览接口真正试采（通过 worker 执行一次查询，或 master 复用 worker adapter 本地执行）并返回样例数据
  - **预览在试采后 SHALL 应用 `transform_script` 对样例数据进行转换，返回转换后的样例**（与正式任务行为一致）
  - 新建采集任务保存前置校验：必须最近一次预览成功
  - 预览成功后可选将任务下发到任意已注册 worker
  - 新增"已注册 worker 列表" HTTP 接口
  - master gRPC 服务端按 `worker_id` 索引活跃流，提供下发 `TaskUpdate` 的入口
  - master gRPC 服务端接收 worker `TaskStatus` 后回写 `CollectorTask` 对应字段
- worker 端：
  - `send_websocket_message` / `report_task_status` 真正通过 `Communicate` 双向流的 `WorkerMessage.task_status` 上报
  - 上报字段补齐：`worker_id`、`task_id`、`task_type`、`status`、`result`、`duration_ms`、`timestamp`、`extra`（含 `rows_count` 等）
  - 保留并复用 `TaskScheduler` 已有的 `task_create` / `task_stop` / `task_pause` / `task_resume` 指令处理
  - **`DatabaseCollectorTask` / `KafkaCollectorTask` 等正式任务在每次执行采集后 SHALL 应用 `transform_script` 转换数据，再上报状态与 `extra.transformed_rows`**
- 共享（master + worker）：
  - 新增轻量 `transform_script` 执行器模块：将 `CollectorTask.transform_script`（Python 源码字符串）安全 exec 为 `transform(data, config) -> data` 可调用对象，供预览与正式任务复用，避免两端重复实现
- 不改动：
  - `master/apps/collector/models.py` 中 `DataSource` / `CollectorTask` 字段定义（已含所需字段）
  - `master/apps/collector/admin.py` 中 DataSourceAdmin / CollectorTaskAdmin 表单字段、列表、操作按钮布局
  - `master/apps/_collector/`（独立 APScheduler 实验模块，不在本联动范围内）
  - **BREAKING** 无：所有改动均为后端联动扩展，不影响现有前端表单结构

## Impact

- Affected specs: `worker-task-scheduler`（worker 端任务调度已实现，本 spec 复用其 `task_create` / `task_status` 通道，不修改其行为契约）
- Affected code:
  - `master/apps/collector/apis.py`（新增预览执行、worker 列表、任务下发路由）
  - `master/apps/collector/admin.py`（仅扩展 preview 路由实现 + 新增 dispatch 路由，不动表单结构）
  - `master/apps/collector/jobs.py`（由空文件改造为 worker 状态回写 / worker 列表查询 / `preview_token` 签发缓存 / transform_script 执行的 helper 模块）
  - `master/grpc_server/server.py`（按 worker_id 索引活跃流；新增 master→worker 推送 TaskUpdate 的方法；处理入站 task_status 并回写 CollectorTask）
  - `worker/grpc/client.py`（`send_websocket_message` 改为通过出站队列异步发送 `WorkerMessage.task_status`；Communicate 的 `message_generator` 改为消费队列）
  - `worker/scheduler/task_scheduler.py`（`report_task_status` 字段补齐 + 通过 grpc_client 出站队列上报）
  - `worker/scheduler/tasks/database_collector_task.py` 与 `worker/scheduler/tasks/kafka_collector_task.py`（在采集后调用共享 `transform_script` 执行器转换数据，再上报状态）
  - `protos/worker.proto`（扩展 `TaskStatus` 与 `TaskUpdate` 消息字段，并重新生成 `worker_pb2*.py`）
  - 新增共享模块 `common/transform_runner.py`（或 `worker/transformer/runner.py` + master 端复用）：实现 `apply_transform(script_src, data, config)` 安全 exec + 转换调用契约

## ADDED Requirements

### Requirement: 保留 master collector 前端配置
系统 SHALL NOT 修改 `master/apps/collector/` 现有的 `DataSource` / `CollectorTask` 模型字段定义、`DataSourceAdmin` / `CollectorTaskAdmin` 的表单字段、列表展示、操作按钮（预览、暂停、恢复）布局。所有联动逻辑 SHALL 通过后端路由扩展与 gRPC 服务端实现，不改前端 AMIS 配置结构。

#### Scenario: 前端配置保持不变
- **WHEN** 实施 collector-worker 联动改造
- **THEN** `master/apps/collector/models.py` 中的 `DataSource` / `CollectorTask` 字段集合与类型保持不变
- **AND** `master/apps/collector/admin.py` 中 DataSourceAdmin / CollectorTaskAdmin 的 `page_schema` / `list_display` / `create_exclude` / `update_exclude` / `read_fields` / `admin_action_maker` 等结构保持不变
- **AND** AMIS `FieldSet(conf)` 表单项（交易日、触发表达式、源数据库、SQL、目标数据库、目标表、数据键值）保持不变

### Requirement: 预览试采（含 transform_script 转换）
系统 SHALL 在 master 端的 `POST /admin/collector/CollectorTaskAdmin/preview` 路由中真正执行一次试采，返回样例数据与执行结果，而不是仅返回源数据库列表。试采方式 SHALL 优先选择已注册 worker 执行（在请求体可选 `worker_id` 字段时），无可用 worker 时回退到 master 本地复用 `worker.adapter.sql_adapter.SqlAdapter` 等执行。试采完成后 SHALL 应用请求体中携带的 `transform_script`（Python 源码字符串）对样例数据进行转换，返回转换后的样例——以与正式任务执行行为保持一致。

#### Scenario: 预览成功（含转换）
- **WHEN** 用户在创建/编辑采集任务对话框中点击"预览"按钮，提交包含 `name` / `collector_type` / `timeout` / `transform_script` / `status` / `conf`（含 `src_datasource`、`sql`、`trigger_expr` 等）的请求体
- **AND** 试采查询返回 N 行原始数据（N ≥ 0），无异常
- **AND** 请求体 `transform_script` 非空时，对该 N 行数据应用 `transform_script` 转换
- **THEN** 响应体 SHALL 包含：`success: true`、`rows`（最多 10 条**转换后**的样例；未提供 `transform_script` 时为原始行）、`raw_rows_count`（转换前行数）、`rows_count`（转换后行数）、`duration_ms`（含采集 + 转换耗时）、`worker_id`（实际执行方）、`preview_token`（用于后续 create 校验）
- **AND** master SHALL 在内存/缓存中保留 `preview_token` 对应的预览结果（30 分钟有效期），含原始样例与转换后样例，供后续 create 接口校验

#### Scenario: 预览失败（采集或转换异常）
- **WHEN** 试采查询抛出异常（连接失败、SQL 语法错误、超时等），或 `transform_script` 在 exec/调用阶段抛出异常（语法错误、运行时错误等）
- **THEN** 响应体 SHALL 包含：`success: false`、`error`（错误类型与消息，含 `transform_error` 标识以区分采集失败与转换失败）、`duration_ms`
- **AND** 不签发 `preview_token`

#### Scenario: transform_script 安全 exec
- **WHEN** master 或 worker 需要执行 `transform_script`
- **THEN** 系统 SHALL 在受限命名空间中 `exec` 该 Python 源码字符串，从中获取名为 `transform` 的可调用对象（签名 `transform(data, config) -> Any`）
- **AND** 限制可访问的内置函数（禁用 `open` / `eval` / `exec` / `__import__` 等危险项，仅保留 `len` / `str` / `int` / `float` / `list` / `dict` / `range` 等基础函数）
- **AND** 执行异常时捕获并返回结构化错误，不污染调用方上下文

### Requirement: 新建任务必须预览成功
系统 SHALL 强制要求新建采集任务在 `POST /admin/collector/CollectorTaskAdmin/item` 提交前，最近一次预览成功。校验通过请求体中携带 `preview_token` 实现；未携带或 `preview_token` 无效/过期时拒绝创建。

#### Scenario: 创建时校验通过
- **WHEN** 用户提交创建请求，请求体中包含的 `preview_token` 在 master 缓存中存在且未过期
- **AND** 缓存的预览结果中 `success == true`
- **THEN** master 正常创建 `CollectorTask` 记录，并将 `status` 初始化为 `TaskStatus.pending`、`exec_status` 初始化为 `ExecStatus.running`、`total_run_count` / `total_failed_count` 初始化为 0
- **AND** 不自动下发任务到 worker（下发由后续 dispatch 操作显式触发）

#### Scenario: 创建时校验失败
- **WHEN** 用户提交创建请求时未携带 `preview_token`，或 `preview_token` 不在 master 缓存中，或对应的预览结果为失败
- **THEN** 返回 `BaseApiOut(status=-1, msg="preview required or preview failed")`，不创建 `CollectorTask` 记录

### Requirement: 预览后可选下发到任意 worker
系统 SHALL 在预览成功后，提供将任务下发到任意已注册 worker 的能力。下发通过新增的 `POST /admin/collector/CollectorTaskAdmin/dispatch` 路由实现，请求体携带 `task_id`（已创建的采集任务 ID）与 `worker_id`（目标 worker）。

#### Scenario: 下发到指定 worker
- **WHEN** 用户在前端预览成功后（或在任务列表中）选择目标 worker 并触发下发
- **AND** 目标 `worker_id` 在 master 的已注册 worker 列表中且状态为 online
- **THEN** master 通过 gRPC `Communicate` 双向流向目标 worker 推送一条 `MasterMessage.task_update` 消息，包含：
  - `task_id`：master 端 `CollectorTask.id`
  - `action`：`"create"`
  - `task_type`：根据 `collector_type` 映射（`database` → `database_collector`、`kafka` → `kafka_collector` 等）
  - `config`：从 `CollectorTask.conf` 与 `DataSource` 派生的 worker 任务配置（`cron_expression` / `adapter_type` / `adapter_config` / `query` / `trade_day_only` 等）
  - `timestamp`：下发时间
- **AND** master 将 `CollectorTask.worker_id` 更新为所选 worker、`job_id` 更新为 master 下发时分配的 job id
- **AND** 不影响其他 worker 上已运行的相同任务

#### Scenario: 下发到不存在的 worker
- **WHEN** 请求的 `worker_id` 不在已注册 worker 列表中，或该 worker 状态非 online
- **THEN** 返回 `BaseApiOut(status=-1, msg="worker not found or offline")`，不下发任务

### Requirement: 已注册 worker 列表接口
系统 SHALL 提供 `GET /admin/collector/CollectorTaskAdmin/workers` 路由，返回当前 master gRPC 服务端已注册的 worker 列表，供前端下发选择使用。

#### Scenario: 列出可用 worker
- **WHEN** 前端请求 `GET /admin/collector/CollectorTaskAdmin/workers`
- **THEN** 响应体 SHALL 包含：`workers`（数组，每项含 `worker_id`、`host`、`port`、`status`、`last_heartbeat`）
- **AND** 列表来源为 `master/grpc_server/server.py` 中 `workers` 字典的当前快照

### Requirement: master 按 worker_id 索引活跃 gRPC 流并下发 TaskUpdate
系统 SHALL 修改 `master/grpc_server/server.py` 的 `WorkerServiceServicer.Communicate` 实现，将活跃流按真实的 `worker_id` 索引（替代当前的 `stream-worker-<timestamp>` 占位 ID），并提供 master 端可调用的 `push_task_update(worker_id, task_update_dict)` 方法，向指定 worker 的活跃流发送 `MasterMessage.task_update`。

#### Scenario: 识别流归属 worker
- **WHEN** worker 建立 `Communicate` 双向流后发送第一条 `WorkerMessage`
- **THEN** master SHALL 从 worker 注册上下文（注册时保存的 `worker_id` → 流映射，或 worker 在首条消息中携带 `worker_id`）确定该流归属的 worker_id
- **AND** 在 `active_streams` 中以真实 `worker_id` 作为键存储该流上下文

#### Scenario: 向指定 worker 下发 TaskUpdate
- **WHEN** master 调用 `push_task_update(worker_id, task_update_dict)`
- **AND** 该 worker_id 在 `active_streams` 中存在
- **THEN** master 通过该流的 `yield` 推送一条 `MasterMessage(task_update=TaskUpdate(...))`
- **AND** 推送失败（流已关闭）时返回 False，调用方可决定重试或报告失败

### Requirement: master 接收 worker TaskStatus 并回写 CollectorTask 字段
系统 SHALL 在 `master/grpc_server/server.py` 的 `Communicate` 处理中，收到 `WorkerMessage.task_status` 后，根据 `task_id` 查找对应 `CollectorTask` 记录，并按 `status` / `result` / `duration_ms` / `extra` 字段回写 `CollectorTask` 的执行统计字段。

#### Scenario: 单次执行成功上报
- **WHEN** worker 通过 `Communicate` 上报 `task_status` 消息，`status == "success"`
- **THEN** master SHALL 定位 `CollectorTask` 记录（按 `task_id` 或 `job_id`），并更新：
  - `exec_status` → `ExecStatus.success`
  - `last_run_time` → 上报 `timestamp`
  - `last_run_status` → `ExecStatus.success`
  - `last_run_duration_ms` → `duration_ms`
  - `total_run_count` += 1
- **AND** 若 `extra.rows_count` 存在，SHALL 一并写入 `CollectorTask` 的运行统计（如有专属字段，复用现有 `total_run_count` / `total_failed_count` 维度）

#### Scenario: 单次执行失败上报
- **WHEN** worker 上报 `task_status` 消息，`status == "failed"`
- **THEN** master SHALL 更新：
  - `exec_status` → `ExecStatus.failed`
  - `last_run_status` → `ExecStatus.failed`
  - `last_run_duration_ms` → `duration_ms`
  - `total_run_count` += 1
  - `total_failed_count` += 1
  - `status` → `TaskStatus.error`（仅在连续失败时标记；首次失败可保持 `running`，由后续策略决定）

#### Scenario: 持续运行任务上报
- **WHEN** worker 上报 `status == "running"`
- **THEN** master SHALL 仅更新 `exec_status` → `ExecStatus.running`，不修改 `total_run_count`
- **AND** 更新 `last_run_time` 为上报 `timestamp`

### Requirement: worker 通过双向流出队上报 TaskStatus
系统 SHALL 修改 `worker/grpc/client.py` 的 `send_websocket_message` 与 `Communicate` 的 `message_generator`，改为从 worker 端的出站队列消费消息，将 `TaskStatus` 包装为 `WorkerMessage(task_status=...)` 通过双向流发送给 master。出站队列 SHALL 支持多线程安全入队（worker 端任务在子线程/子进程中触发上报）。

#### Scenario: worker 上报任务状态
- **WHEN** `TaskScheduler.report_task_status` 被调用（任务执行成功/失败/运行中）
- **THEN** worker 构造 `TaskStatus` 消息（`task_id` / `status` / `message` / `timestamp`，并通过扩展字段携带 `task_type` / `duration_ms` / `result` / `rows_count`）
- **AND** 将 `WorkerMessage(task_status=...)` 入队到出站队列
- **AND** `Communicate` 的 `message_generator` 从队列取出该消息并通过 `yield` 发送给 master
- **AND** 上报失败（master 流断开）时本地丢弃并记日志，不阻塞任务执行

#### Scenario: 队列非阻塞入队
- **WHEN** worker 子线程/子进程并发上报状态
- **THEN** 入队操作 SHALL 线程安全且非阻塞（使用 `queue.Queue` 或 `collections.deque` + 锁），队列满时丢弃最旧消息并记日志，避免任务执行线程被阻塞

### Requirement: 正式任务执行 transform_script 转换数据
系统 SHALL 在 worker 端的 `DatabaseCollectorTask` / `KafkaCollectorTask` 等正式任务执行流程中，每次完成采集（执行 SQL / 消费 Kafka 消息）后、上报状态前，应用任务配置中携带的 `transform_script` 对采集结果进行转换。转换逻辑 SHALL 复用 master / worker 共享的 `transform_script` 执行器，确保与预览阶段转换行为一致。

#### Scenario: 任务执行成功并应用 transform_script
- **WHEN** `DatabaseCollectorTask` 按 cron 表达式触发执行，SQL 查询返回 N 行原始数据
- **AND** 任务 config 中携带 `transform_script`（非空 Python 源码字符串）
- **THEN** worker SHALL 调用共享执行器加载 `transform_script`，对 N 行原始数据调用 `transform(data, config)` 获得转换后数据
- **AND** 上报 `TaskStatus` 时 `status == "success"`、`extra.transformed_rows` 含转换后行数（或样例前 3 行）、`extra.raw_rows_count` 含原始行数
- **AND** 转换异常时上报 `status == "failed"`、`extra.error_kind == "transform_error"`、`message` 含异常信息，但采集部分已成功（避免丢失采集数据，可在 extra 中携带原始行数）

#### Scenario: 未配置 transform_script 的任务
- **WHEN** 任务 config 中 `transform_script` 为空或未提供
- **THEN** worker SHALL 跳过转换步骤，直接上报采集原始数据
- **AND** `extra.transformed_rows` 不存在或与 `extra.raw_rows_count` 相同

#### Scenario: 共享 transform_script 执行器
- **WHEN** master 预览阶段或 worker 正式任务阶段需要执行 `transform_script`
- **THEN** 系统 SHALL 使用同一份执行器实现（位于 master 与 worker 共享的模块路径，或在两端分别提供相同接口契约的轻量实现）
- **AND** 执行器接口契约：`apply_transform(script_src: str, data: Any, config: dict) -> tuple[bool, Any, Optional[str]]`，返回 `(是否成功, 转换后数据或错误信息, 错误类型)`

## MODIFIED Requirements

### Requirement: 预览接口语义扩展（修改自 worker-task-scheduler spec 中未明确覆盖的 master 端预览能力）
原 `master/apps/collector/admin.py` 的 `preview` 路由仅返回源数据库列表，未真正试采。本次修改为：`preview` 路由 SHALL 真正执行一次试采并返回样例数据 + `preview_token`，语义由"列出源数据库"升级为"试采 + 签发预览凭证"。

## REMOVED Requirements

无（本 spec 不移除任何已有能力）
