# Tasks

- [ ] Task 1: 扩展 proto 消息字段并重新生成 stub
  - [ ] 在 `protos/worker.proto` 中扩展 `TaskStatus` 消息：新增 `string task_type`、`string worker_id`、`double duration_ms`、`string result`、`map<string,string> extra` 字段（保留原有 `task_id` / `status` / `message` / `timestamp`）
  - [ ] 在 `protos/worker.proto` 中扩展 `TaskUpdate` 消息：将 `config` 由 `map<string,string>` 改为 `string`（承载 JSON 序列化后的复杂 config），并新增 `string worker_id` 字段标识目标 worker
  - [ ] 运行 `python scripts/generate_grpc_code.py` 重新生成 `master/grpc_server/worker_pb2*.py` 与 `worker/grpc/worker_pb2*.py`
  - [ ] 验证生成的 stub 在 master / worker 两端均可正常 import

- [ ] Task 2: master gRPC 服务端按 worker_id 索引活跃流
  - [ ] 修改 `master/grpc_server/server.py` 的 `WorkerServiceServicer.Communicate`，将 `active_streams` 的键由 `stream-worker-<timestamp>` 改为真实 `worker_id`
  - [ ] 在 `RegisterWorker` 中将 `worker_id` → 注册上下文关联，使后续 Communicate 流可解析归属（通过 worker 在首条消息携带 worker_id，或通过 channel peer metadata）
  - [ ] 新增 `push_task_update(worker_id: str, task_update_dict: dict) -> bool` 方法，向指定 worker 的活跃流推送 `MasterMessage(task_update=...)`
  - [ ] 处理流关闭时清理 `active_streams` 中对应 worker_id 的条目

- [ ] Task 3: master gRPC 服务端接收 TaskStatus 并回写 CollectorTask
  - [ ] 在 `Communicate` 中收到 `WorkerMessage.task_status` 时，调用新增的 `_handle_task_status(task_status)` 方法
  - [ ] 实现 `_handle_task_status`：根据 `task_id`（或 `extra.job_id`）查找 `CollectorTask`，按 `status`（success / failed / running）更新 `exec_status` / `last_run_time` / `last_run_status` / `last_run_duration_ms` / `total_run_count` / `total_failed_count` / `status` 字段
  - [ ] db session 通过 master app lifespan 中初始化的全局 async_sessionmaker 获取；若 Communicate 运行在 grpc 线程，使用 `asyncio.run_coroutine_threadsafe` 提交到 master 事件循环
  - [ ] 处理 task_id 找不到的情况：仅记日志，不抛异常（避免击穿 gRPC 流）

- [ ] Task 4: master 端新增已注册 worker 列表接口
  - [ ] 在 `master/apps/collector/apis.py` 中新增 `GET /api/collector/workers` 路由
  - [ ] 路由从 `master/grpc_server/server.py` 暴露的 `workers` 字典读取快照（新增 `list_workers()` 辅助函数）
  - [ ] 返回字段：`worker_id`、`host`、`port`、`status`、`last_heartbeat`、`version`

- [ ] Task 5: master 端预览接口真正试采 + 签发 preview_token
  - [ ] 修改 `master/apps/collector/admin.py` 中 `preview` 路由：
    - 解析 `conf` 中的 `src_datasource`、`sql`、`timeout`、`trade_day_only` 等字段
    - 若请求体含 `worker_id` 且该 worker 在线：构造 worker 任务 config（adapter_type / adapter_config / query），通过新增的 `dispatch_preview_to_worker` 调用走 worker 临时执行一次
    - 否则回退到 master 本地复用 `worker.adapter.sql_adapter.SqlAdapter`（import 时兼容 worker 包不可用情况）执行
    - 返回 `{success, rows, rows_count, duration_ms, worker_id, preview_token}` 或 `{success:false, error, duration_ms}`
  - [ ] 在 `master/apps/collector/jobs.py` 中实现 `preview_token` 签发与缓存（内存 dict + 30 分钟 TTL + 简单锁），含 `issue_preview_token(payload)`、`consume_preview_token(token) -> Optional[dict]`、后台清理过期 token 的轻量逻辑
  - [ ] 预览失败时不签发 token

- [ ] Task 6: master 端创建任务前置预览校验
  - [ ] 修改 `master/apps/collector/admin.py` 的创建路由（`on_create_pre` 钩子或自定义 `item` POST 路由），要求请求体含 `preview_token`
  - [ ] 通过 `jobs.consume_preview_token(token)` 校验：token 有效且 `success==true` 才允许继续；否则返回 `BaseApiOut(status=-1, msg="preview required or preview failed")`
  - [ ] 校验通过后正常走默认创建流程；不在此步骤下发任务到 worker（下发由 Task 7 显式触发）

- [ ] Task 7: master 端任务下发到指定 worker 路由
  - [ ] 在 `master/apps/collector/admin.py` 新增 `POST /admin/collector/CollectorTaskAdmin/dispatch` 路由，接收 `{task_id, worker_id}`
  - [ ] 校验 `worker_id` 在 `master/grpc_server/server.py` 的 `workers` 中且状态为 online；否则返回 `BaseApiOut(status=-1, msg="worker not found or offline")`
  - [ ] 根据 `CollectorTask.collector_type` 映射 worker 任务类型（`database` → `database_collector`、`kafka` → `kafka_collector` 等）
  - [ ] 从 `CollectorTask.conf` + 关联 `DataSource` 派生 worker config（`cron_expression` from `trigger_expr`、`adapter_type` from `database_type`、`adapter_config` from DataSource.url/username/password、`query` from `conf.sql`、`trade_day_only` from `conf.is_trading_day`）
  - [ ] 调用 `master/grpc_server/server.py` 新增的 `push_task_update(worker_id, task_update_dict)` 推送 `MasterMessage(task_update=...)`
  - [ ] 推送成功后更新 `CollectorTask.worker_id` 与 `job_id`（job_id 使用 master 分配的 UUID），返回 `BaseApiOut(data={worker_id, job_id})`

- [ ] Task 8: worker gRPC 客户端出站队列 + 真实 TaskStatus 上报
  - [ ] 在 `worker/grpc/client.py` 的 `CentralGrpcClient` 中新增 `self._outbound_queue: queue.Queue` 与 `_enqueue_outbound(msg)` 非阻塞入队方法（满时丢弃最旧消息 + 日志）
  - [ ] 修改 `_start_communicate_stream` 的 `message_generator`：循环从 `_outbound_queue.get(timeout=30)` 取消息 yield；同时保留原有 30 秒 Ping 心跳
  - [ ] 重写 `send_websocket_message(message)`：构造 `worker_pb2.TaskStatus`（task_id / status / message / timestamp / task_type / worker_id / duration_ms / result / extra），包装为 `WorkerMessage(task_status=...)` 入队
  - [ ] 流断开时（`_connected=False`）入队仍成功，但下次重连后尽快发送（不强制持久化）

- [ ] Task 9: worker TaskScheduler 上报字段补齐
  - [ ] 修改 `worker/scheduler/task_scheduler.py` 的 `report_task_status`：将 `result` 截断为合理长度（避免大对象通过 gRPC），并将 `rows_count` / `error_message` 等通过 `extra` map 携带
  - [ ] 调用 `self._grpc_client.send_websocket_message(message)` 时确保使用扩展后的 TaskStatus 字段
  - [ ] 在 `worker/main.py` 中确认 `TaskScheduler(grpc_client=...)` 已注入，且 `_central_client` 仍为 None（保持当前架构，避免重复上报）

- [ ] Task 10: 联动冒烟测试与端到端验证
  - [ ] 编写脚本或 pytest 用例：启动 master gRPC + HTTP，启动一个 worker，调用 `GET /api/collector/workers` 验证 worker 已注册
  - [ ] 调用 `POST /admin/collector/CollectorTaskAdmin/preview` 提交测试 SQL 配置，验证返回 `success==true` 与 `preview_token`
  - [ ] 调用 `POST /admin/collector/CollectorTaskAdmin/item` 携带 `preview_token` 创建任务，验证创建成功
  - [ ] 调用 `POST /admin/collector/CollectorTaskAdmin/dispatch` 下发到 worker，验证 worker 端 TaskScheduler 收到 `task_create` 并启动 DatabaseCollectorTask
  - [ ] 等待 cron 触发或手动触发一次执行，验证 master `CollectorTask.last_run_*` / `total_run_count` 字段被回写
  - [ ] 验证不带 `preview_token` 创建任务时返回 `-1` 拒绝

# Task Dependencies
- Task 1（proto + stub）是 Task 2、3、8、9 的前置依赖
- Task 2（master 活跃流索引）是 Task 7（下发）的前置依赖
- Task 3（master 回写）依赖 Task 1、Task 8/9（worker 真实上报）
- Task 5（预览试采）依赖 Task 4（worker 列表，用于试采时选择执行方）；与 Task 6（创建校验）紧耦合：Task 6 依赖 Task 5 签发的 preview_token
- Task 7（下发）依赖 Task 2、Task 5（预览产生的 task 已创建）
- Task 8（worker 出站队列）依赖 Task 1
- Task 9（worker 上报字段）依赖 Task 1、Task 8
- Task 10（端到端验证）依赖全部前序任务完成
- 可并行：Task 2 + Task 4 + Task 5（master 端，互不耦合）；Task 8 + Task 9（worker 端，紧耦合可合并实现）
