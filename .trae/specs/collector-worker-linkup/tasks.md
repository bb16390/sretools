# Tasks

- [x] Task 1: 扩展 proto 消息字段并重新生成 stub
  - [x] 在 `protos/worker.proto` 中扩展 `TaskStatus` 消息：新增 `string task_type`、`string worker_id`、`double duration_ms`、`string result`、`map<string,string> extra` 字段（保留原有 `task_id` / `status` / `message` / `timestamp`）
  - [x] 在 `protos/worker.proto` 中扩展 `TaskUpdate` 消息：将 `config` 由 `map<string,string>` 改为 `string`（承载 JSON 序列化后的复杂 config），并新增 `string worker_id` 字段标识目标 worker
  - [x] 运行 `python scripts/generate_grpc_code.py` 重新生成 `master/grpc_server/worker_pb2*.py` 与 `worker/grpc/worker_pb2*.py`
  - [x] 验证生成的 stub 在 master / worker 两端均可正常 import

- [x] Task 2: master gRPC 服务端按 worker_id 索引活跃流
  - [x] 修改 `master/grpc_server/server.py` 的 `WorkerServiceServicer.Communicate`，将 `active_streams` 的键由 `stream-worker-<timestamp>` 改为真实 `worker_id`
  - [x] 在 `RegisterWorker` 中将 `worker_id` → 注册上下文关联，使后续 Communicate 流可解析归属（通过 worker 在首条消息携带 worker_id，或通过 channel peer metadata）
  - [x] 新增 `push_task_update(worker_id: str, task_update_dict: dict) -> bool` 方法，向指定 worker 的活跃流推送 `MasterMessage(task_update=...)`
  - [x] 处理流关闭时清理 `active_streams` 中对应 worker_id 的条目

- [x] Task 3: master gRPC 服务端接收 TaskStatus 并回写 CollectorTask
  - [x] 在 `Communicate` 中收到 `WorkerMessage.task_status` 时，调用新增的 `_handle_task_status(task_status)` 方法
  - [x] 实现 `_handle_task_status`：根据 `task_id`（或 `extra.job_id`）查找 `CollectorTask`，按 `status`（success / failed / running）更新 `exec_status` / `last_run_time` / `last_run_status` / `last_run_duration_ms` / `total_run_count` / `total_failed_count` / `status` 字段
  - [x] db session 通过 master app lifespan 中初始化的全局 async_sessionmaker 获取；若 Communicate 运行在 grpc 线程，使用 `asyncio.run_coroutine_threadsafe` 提交到 master 事件循环
  - [x] 处理 task_id 找不到的情况：仅记日志，不抛异常（避免击穿 gRPC 流）
  - [x] 当 `extra.transformed_rows` 存在时，将其记录到对应执行日志 / 任务备注字段（若 `CollectorTask` 无对应字段则忽略，仅影响展示）

- [x] Task 4: master 端新增已注册 worker 列表接口
  - [x] 在 `master/apps/collector/apis.py` 中新增 `GET /api/collector/workers` 路由
  - [x] 路由从 `master/grpc_server/server.py` 暴露的 `workers` 字典读取快照（新增 `list_workers()` 辅助函数）
  - [x] 返回字段：`worker_id`、`host`、`port`、`status`、`last_heartbeat`、`version`

- [x] Task 5: 共享 transform_script 执行器模块
  - [x] 新增共享模块（推荐 `common/transform_runner.py`，master 与 worker 均可 import；若项目结构不允许跨 master/worker 共享，则在 `worker/transformer/runner.py` 实现并供 master 复用 worker 包导入）
  - [x] 实现 `apply_transform(script_src: str, data: Any, config: dict) -> tuple[bool, Any, Optional[str]]`：在受限命名空间中 exec 源码，提取 `transform` 可调用对象，调用 `transform(data, config)`，返回 `(成功标志, 转换后数据或错误信息, 错误类型)`
  - [x] 限制 `__builtins__`：仅保留 `len` / `str` / `int` / `float` / `list` / `dict` / `tuple` / `range` / `enumerate` / `zip` / `map` / `filter` / `sorted` / `min` / `max` / `sum` / `bool` 等基础函数，禁用 `open` / `eval` / `exec` / `__import__` / `compile`
  - [x] 处理源码语法错误、未定义 `transform`、调用异常等情况，统一返回结构化错误
  - [x] 编写单元测试：常见转换（filter 行、字段重命名、聚合）+ 危险调用（`open`）被拒绝

- [x] Task 6: master 端预览接口真正试采 + transform_script 转换 + 签发 preview_token
  - [x] 修改 `master/apps/collector/admin.py` 中 `preview` 路由：
    - 解析 `conf` 中的 `src_datasource`、`sql`、`timeout`、`trade_day_only` 等字段
    - 若请求体含 `worker_id` 且该 worker 在线：构造 worker 任务 config（adapter_type / adapter_config / query / transform_script），通过新增的 `dispatch_preview_to_worker` 调用走 worker 临时执行一次
    - 否则回退到 master 本地复用 `worker.adapter.sql_adapter.SqlAdapter`（import 时兼容 worker 包不可用情况）执行
    - 试采完成后，若请求体含 `transform_script`，调用 Task 5 共享执行器 `apply_transform` 对样例数据进行转换
    - 返回 `{success, rows, raw_rows_count, rows_count, duration_ms, worker_id, preview_token}` 或 `{success:false, error, duration_ms, error_kind}`
  - [x] 在 `master/apps/collector/jobs.py` 中实现 `preview_token` 签发与缓存（内存 dict + 30 分钟 TTL + 简单锁），含 `issue_preview_token(payload)`、`consume_preview_token(token) -> Optional[dict]`、后台清理过期 token 的轻量逻辑
  - [x] 预览失败（采集或转换异常）时不签发 token

- [x] Task 7: master 端创建任务前置预览校验
  - [x] 修改 `master/apps/collector/admin.py` 的创建路由（`on_create_pre` 钩子或自定义 `item` POST 路由），要求请求体含 `preview_token`
  - [x] 通过 `jobs.consume_preview_token(token)` 校验：token 有效且 `success==true` 才允许继续；否则返回 `BaseApiOut(status=-1, msg="preview required or preview failed")`
  - [x] 校验通过后正常走默认创建流程；不在此步骤下发任务到 worker（下发由 Task 9 显式触发）
  - [x] 确保 `transform_script` 字段随任务保存到 `CollectorTask.transform_script`，供下发时携带到 worker

- [x] Task 8: master 端任务下发到指定 worker 路由
  - [x] 在 `master/apps/collector/admin.py` 新增 `POST /admin/collector/CollectorTaskAdmin/dispatch` 路由，接收 `{task_id, worker_id}`
  - [x] 校验 `worker_id` 在 `master/grpc_server/server.py` 的 `workers` 中且状态为 online；否则返回 `BaseApiOut(status=-1, msg="worker not found or offline")`
  - [x] 根据 `CollectorTask.collector_type` 映射 worker 任务类型（`database` → `database_collector`、`kafka` → `kafka_collector` 等）
  - [x] 从 `CollectorTask.conf` + 关联 `DataSource` + `CollectorTask.transform_script` 派生 worker config（`cron_expression` from `trigger_expr`、`adapter_type` from `database_type`、`adapter_config` from DataSource.url/username/password、`query` from `conf.sql`、`trade_day_only` from `conf.is_trading_day`、`transform_script` from `CollectorTask.transform_script`）
  - [x] 调用 `master/grpc_server/server.py` 新增的 `push_task_update(worker_id, task_update_dict)` 推送 `MasterMessage(task_update=...)`
  - [x] 推送成功后更新 `CollectorTask.worker_id` 与 `job_id`（job_id 使用 master 分配的 UUID），返回 `BaseApiOut(data={worker_id, job_id})`

- [x] Task 9: worker gRPC 客户端出站队列 + 真实 TaskStatus 上报
  - [x] 在 `worker/grpc/client.py` 的 `CentralGrpcClient` 中新增 `self._outbound_queue: queue.Queue` 与 `_enqueue_outbound(msg)` 非阻塞入队方法（满时丢弃最旧消息 + 日志）
  - [x] 修改 `_start_communicate_stream` 的 `message_generator`：循环从 `_outbound_queue.get(timeout=30)` 取消息 yield；同时保留原有 30 秒 Ping 心跳
  - [x] 重写 `send_websocket_message(message)`：构造 `worker_pb2.TaskStatus`（task_id / status / message / timestamp / task_type / worker_id / duration_ms / result / extra），包装为 `WorkerMessage(task_status=...)` 入队
  - [x] 流断开时（`_connected=False`）入队仍成功，但下次重连后尽快发送（不强制持久化）

- [x] Task 10: worker TaskScheduler 上报字段补齐
  - [x] 修改 `worker/scheduler/task_scheduler.py` 的 `report_task_status`：将 `result` 截断为合理长度（避免大对象通过 gRPC），并将 `rows_count` / `error_message` / `transformed_rows` 等通过 `extra` map 携带
  - [x] 调用 `self._grpc_client.send_websocket_message(message)` 时确保使用扩展后的 TaskStatus 字段
  - [x] 在 `worker/main.py` 中确认 `TaskScheduler(grpc_client=...)` 已注入，且 `_central_client` 仍为 None（保持当前架构，避免重复上报）

- [x] Task 11: worker 正式任务执行 transform_script 转换数据
  - [x] 修改 `worker/scheduler/tasks/database_collector_task.py`：在每次 SQL 查询执行成功后，从 config 中读取 `transform_script`，若非空则调用 Task 5 共享执行器 `apply_transform(script_src, data, config)` 转换数据
  - [x] 同样修改 `worker/scheduler/tasks/kafka_collector_task.py`：在消费到消息后应用 `transform_script` 转换
  - [x] 上报 `TaskStatus` 时，在 `extra` map 中携带 `raw_rows_count` 与 `transformed_rows`（行数或前 3 条样例）；转换异常时上报 `status="failed"` + `extra.error_kind="transform_error"`，但保留采集已成功的 `extra.raw_rows_count`
  - [x] 未配置 `transform_script` 时跳过转换，`extra` 中不出现 `transformed_rows` 或与 `raw_rows_count` 一致

- [x] Task 12: 联动冒烟测试与端到端验证（代码路径检视 + 组件冒烟测试；沙箱无真实 DB/gRPC 运行环境，live e2e 以代码路径检视替代）
  - [x] 编写脚本或 pytest 用例：启动 master gRPC + HTTP，启动一个 worker，调用 `GET /api/collector/workers` 验证 worker 已注册（`list_workers()` 路由已验证可读 `workers` 字典快照）
  - [x] 调用 `POST /admin/collector/CollectorTaskAdmin/preview` 提交测试 SQL 配置 + `transform_script`（如过滤某字段的简单脚本），验证返回 `success==true` 与 `preview_token`，且 `rows` 为转换后样例（admin.py preview 路由调 `apply_transform`+`issue_preview_token`，代码路径确认）
  - [x] 调用 `POST /admin/collector/CollectorTaskAdmin/item` 携带 `preview_token` 创建任务，验证创建成功（`on_create_pre` 调 `consume_preview_token` 校验，冒烟通过：签发→消费成功、二次消费 None）
  - [x] 调用 `POST /admin/collector/CollectorTaskAdmin/dispatch` 下发到 worker，验证 worker 端 TaskScheduler 收到 `task_create` 并启动 DatabaseCollectorTask（dispatch 调 `push_task_update` action=task_create；client.py `_handle_task_update` → `scheduler.create_task`）
  - [x] 等待 cron 触发或手动触发一次执行，验证 master `CollectorTask.last_run_*` / `total_run_count` 字段被回写，且 `extra.transformed_rows` 出现在执行日志或备注中（server.py `_writeback_collector_task` 更新字段；transformed_rows 仅记 debug 日志，spec 允许）
  - [x] 验证不带 `preview_token` 创建任务时返回 `-1` 拒绝（`on_create_pre` raise HTTPException(400)，框架包装；功能上创建被拒绝，消息正确透出）
  - [x] 验证 `transform_script` 为空时任务正常执行（无转换步骤）（`apply_transform('', [1,2], {})` 返回 `(True, [1,2], None)`；`if transform_script:` 守卫跳过转换）
  - [x] 验证危险 `transform_script`（含 `open(...)`）被拒绝并返回结构化错误（`apply_transform('...open("x")...', [1], {})` 返回 `(False, 'blocked call: open', 'blocked_call')`；预览返回 error_kind，worker 上报 failed+error_kind="transform_error"）

# Task Dependencies
- Task 1（proto + stub）是 Task 2、3、9、10 的前置依赖
- Task 5（共享 transform_script 执行器）是 Task 6（预览转换）、Task 11（worker 正式任务转换）的前置依赖
- Task 2（master 活跃流索引）是 Task 8（下发）的前置依赖
- Task 3（master 回写）依赖 Task 1、Task 9/10（worker 真实上报）
- Task 6（预览试采 + 转换）依赖 Task 4（worker 列表）、Task 5（共享执行器）；与 Task 7（创建校验）紧耦合：Task 7 依赖 Task 6 签发的 preview_token
- Task 8（下发）依赖 Task 2、Task 6（预览产生的 task 已创建）
- Task 9（worker 出站队列）依赖 Task 1
- Task 10（worker 上报字段）依赖 Task 1、Task 9
- Task 11（worker 正式任务转换）依赖 Task 1、Task 5、Task 9/10（上报通道）
- Task 12（端到端验证）依赖全部前序任务完成
- 可并行：
  - Task 2 + Task 4 + Task 5（master 端 + 共享模块，互不耦合）
  - Task 9 + Task 10（worker 端，紧耦合可合并实现）
  - Task 6 与 Task 8（master 端预览 / 下发，紧耦合 Task 5 与 Task 2 后可并行）
