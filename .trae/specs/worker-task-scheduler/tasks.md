# Tasks

- [ ] Task 1: 创建 `worker/scheduler/` 模块目录结构和基础文件
  - [ ] 创建 `worker/scheduler/__init__.py`
  - [ ] 创建 `worker/scheduler/base_task.py`：任务抽象基类，定义 TaskStatus 枚举和 BaseTask 抽象类（含 `start()`、`stop()`、`pause()`、`resume()` 方法签名，以及 `task_id`、`task_type`、`config`、`status` 属性）
  - [ ] 创建 `worker/scheduler/task_scheduler.py`：TaskScheduler 类骨架，含任务注册表（dict）和基本增删查方法

- [ ] Task 2: 实现实时日志采集任务 LogCollectorTask
  - [ ] 在 `worker/scheduler/tasks/` 下创建 `log_collector_task.py`
  - [ ] 继承 BaseTask，封装现有 `worker/collector/log_collector.py` 的 LogCollector
  - [ ] 实现 `start()` → 创建 LogCollector 实例并启动采集线程
  - [ ] 实现 `stop()` → 停止采集线程，清理队列
  - [ ] 实现 `pause()` / `resume()` → 暂停/恢复采集（通过事件标志控制）

- [ ] Task 3: 实现日志转指标任务 MetricConverterTask
  - [ ] 在 `worker/scheduler/tasks/` 下创建 `metric_converter_task.py`
  - [ ] 继承 BaseTask，封装现有 `worker/metrics/metric_converter.py` 的 MetricConverter
  - [ ] 实现 `start()` → 创建 MetricConverter 实例并启动转换/聚合线程
  - [ ] 实现 `stop()` → 停止转换/聚合线程，处理队列中残留数据
  - [ ] 实现 `pause()` / `resume()` → 暂停/恢复转换（通过事件标志控制）

- [ ] Task 4: 实现定时数据库采集任务 DatabaseCollectorTask
  - [ ] 在 `worker/scheduler/tasks/` 下创建 `database_collector_task.py`
  - [ ] 继承 BaseTask，利用现有 Adapter 体系（通过 AdapterManager 获取数据库适配器）
  - [ ] 实现 cron 表达式解析（使用 `croniter` 库）计算下次执行时间
  - [ ] 实现 `start()` → 启动调度循环，在 cron 触发时间执行 SQL 查询
  - [ ] 实现 `stop()` → 取消定时调度，等待当前执行完成
  - [ ] 单次执行完成后自动上报任务状态（通过回调通知 TaskScheduler）

- [ ] Task 5: 实现 TaskScheduler 核心调度逻辑
  - [ ] 实现 `create_task(task_type, config)` → 根据类型创建 Task 实例并注册
  - [ ] 实现 `stop_task(task_id)` → 查找并停止指定任务
  - [ ] 实现 `pause_task(task_id)` / `resume_task(task_id)` → 暂停/恢复指定任务
  - [ ] 实现 `get_task(task_id)` / `list_tasks()` → 查询任务状态
  - [ ] 实现任务工厂：`task_type` → 对应 Task 类的映射注册机制

- [ ] Task 6: 实现任务状态上报功能
  - [ ] 在 TaskScheduler 中实现 `report_task_status(task_id, status, result, duration_ms)`
  - [ ] 构造符合 spec 定义的上报消息 JSON 格式
  - [ ] 通过 CentralClient 的 `send_websocket_message()` 异步发送
  - [ ] 为持续运行类任务（LogCollectorTask / MetricConverterTask）添加定时上报逻辑

- [ ] Task 7: 扩展 CentralClient，支持接收并转发调度指令
  - [ ] 在 CentralClient 中新增 `register_task_scheduler(scheduler)` 方法，持有 TaskScheduler 引用
  - [ ] 扩展 `_handle_task_update()` 方法，解析指令类型（task_create / task_stop / task_pause / task_resume）并调用 TaskScheduler 对应方法
  - [ ] 在 `_handle_websocket_message()` 中注册新的消息处理器映射

- [ ] Task 8: 改造 Worker 主入口，集成 TaskScheduler
  - [ ] 修改 `worker/main.py`，在 `Worker.__init__()` 中初始化 TaskScheduler
  - [ ] 将 TaskScheduler 注册到 CentralClient
  - [ ] 移除原有的模拟主循环 `while True: sleep(10)`，改为由 TaskScheduler 驱动
  - [ ] 确保 Worker 关闭时优雅停止所有运行中的任务

# Task Dependencies
- Task 2、3、4 均依赖 Task 1（BaseTask 基类定义）
- Task 5 依赖 Task 1
- Task 6 依赖 Task 5（TaskScheduler 核心调度逻辑就绪）
- Task 7 依赖 Task 5（需要 TaskScheduler 实例才能注册）
- Task 8 依赖 Task 5、7（TaskScheduler 和 CentralClient 扩展都就绪后集成）
- Task 2 和 Task 3 互相独立，可并行开发
- Task 4 独立于 Task 2、3，可并行开发