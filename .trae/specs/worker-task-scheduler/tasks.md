# Tasks

- [x] Task 1: 创建 `worker/scheduler/` 模块目录结构和基础文件
  - [x] 创建 `worker/scheduler/__init__.py`
  - [x] 创建 `worker/scheduler/base_task.py`：定义 `ExecutionMode` 枚举（THREAD / PROCESS）、`TaskStatus` 枚举（IDLE / RUNNING / PAUSED / STOPPED / FAILED）和 `BaseTask` 抽象类（含 `execution_mode` 属性，以及 `start()`、`stop()`、`pause()`、`resume()` 抽象方法）
  - [x] 创建 `worker/scheduler/task_scheduler.py`：TaskScheduler 类骨架，含任务注册表（dict）、进程监控循环和基本增删查方法

- [x] Task 2: 实现实时日志采集任务 LogCollectorTask
  - [x] 在 `worker/scheduler/tasks/` 下创建 `__init__.py` 和 `log_collector_task.py`
  - [x] 继承 BaseTask，封装现有 `worker/collector/log_collector.py` 的 LogCollector
  - [x] 实现 `_run()` 核心执行逻辑，包含采集循环（通过 `threading.Event` / `multiprocessing.Event` 控制暂停和停止）
  - [x] 实现 `start()` → 根据 `execution_mode` 创建线程或进程运行 `_run()`，默认 `"process"`
  - [x] 实现 `stop()` → 设置停止事件，等待线程/进程结束，超时后 force kill（进程模式调 `terminate()`）
  - [x] 实现 `pause()` / `resume()` → 通过事件标志暂停/恢复采集循环

- [x] Task 3: 实现日志转指标任务 MetricConverterTask
  - [x] 在 `worker/scheduler/tasks/` 下创建 `metric_converter_task.py`
  - [x] 继承 BaseTask，封装现有 `worker/metrics/metric_converter.py` 的 MetricConverter
  - [x] 实现 `_run()` 核心执行逻辑，包含转换循环和聚合循环（通过 Event 控制暂停和停止）
  - [x] 实现 `start()` → 根据 `execution_mode` 创建线程或进程运行 `_run()`，默认 `"process"`
  - [x] 实现 `stop()` → 设置停止事件，等待线程/进程结束，处理队列中残留数据
  - [x] 实现 `pause()` / `resume()` → 通过事件标志暂停/恢复转换循环

- [x] Task 4: 实现定时数据库采集任务 DatabaseCollectorTask
  - [x] 在 `worker/scheduler/tasks/` 下创建 `database_collector_task.py`
  - [x] 继承 BaseTask，利用现有 Adapter 体系（通过 AdapterManager 获取数据库适配器）
  - [x] 实现 cron 表达式解析（使用 `croniter` 库）计算下次执行时间
  - [x] 实现 `start()` → 根据 `execution_mode` 创建线程或进程启动调度循环，在 cron 触发时间执行 SQL 查询，默认 `"thread"`
  - [x] 实现 `stop()` → 取消定时调度，等待当前执行完成
  - [x] 单次执行完成后自动上报任务状态（通过回调通知 TaskScheduler）

- [x] Task 5: 实现 TaskScheduler 核心调度逻辑（含多进程/多线程管理）
  - [x] 实现 `create_task(task_type, config)` → 根据类型创建 Task 实例，读取 `execution_mode` 配置启动任务，注册到内部管理表
  - [x] 实现 `stop_task(task_id)` → 查找任务，根据其 `execution_mode` 调用对应停止逻辑（线程 join / 进程 terminate）
  - [x] 实现 `pause_task(task_id)` / `resume_task(task_id)` → 暂停/恢复指定任务
  - [x] 实现 `get_task(task_id)` / `list_tasks()` → 查询任务状态
  - [x] 实现任务工厂：`task_type` → 对应 Task 类的映射注册机制，含默认 `execution_mode` 配置
  - [x] 实现进程存活监控：后台线程定期轮询各进程模式任务的 `Process.is_alive()`，发现异常退出时标记 FAILED 并上报

- [x] Task 6: 实现任务状态上报功能
  - [x] 在 TaskScheduler 中实现 `report_task_status(task_id, status, result, duration_ms)`
  - [x] 构造符合 spec 定义的上报消息 JSON 格式（含 `execution_mode` 字段）
  - [x] 通过 CentralClient 的 `send_websocket_message()` 异步发送
  - [x] 为持续运行类任务（LogCollectorTask / MetricConverterTask）添加定时上报逻辑（默认30秒间隔）

- [x] Task 7: 扩展 CentralClient，支持接收并转发调度指令
  - [x] 在 CentralClient 中新增 `register_task_scheduler(scheduler)` 方法，持有 TaskScheduler 引用
  - [x] 扩展 `_handle_task_update()` 方法，解析指令类型（task_create / task_stop / task_pause / task_resume）并调用 TaskScheduler 对应方法
  - [x] 在 `_handle_websocket_message()` 中注册新的消息处理器映射

- [x] Task 8: 改造 Worker 主入口，集成 TaskScheduler
  - [x] 修改 `worker/main.py`，在 `Worker.__init__()` 中初始化 TaskScheduler
  - [x] 将 TaskScheduler 注册到 CentralClient
  - [x] 移除原有的模拟主循环 `while True: sleep(10)`，改为由 TaskScheduler 驱动的事件循环
  - [x] 确保 Worker 关闭时（KeyboardInterrupt）优雅停止所有运行中的任务（先发停止信号，再 join/terminate 所有线程/进程）

- [x] Task 9: 添加 `croniter` 依赖
  - [x] 在 `pyproject.toml` 中添加 `croniter` 依赖

# Task Dependencies
- Task 2、3、4 均依赖 Task 1（BaseTask 基类定义）
- Task 5 依赖 Task 1
- Task 6 依赖 Task 5（TaskScheduler 核心调度逻辑就绪）
- Task 7 依赖 Task 5（需要 TaskScheduler 实例才能注册）
- Task 8 依赖 Task 5、7（TaskScheduler 和 CentralClient 扩展都就绪后集成）
- Task 9 独立，可提前并行执行
- Task 2 和 Task 3 互相独立，可并行开发
- Task 4 独立于 Task 2、3，可并行开发