# 清理 worker/collector 目录计划

## 摘要
清理空的 `worker/collector/` 目录并验证无其他代码引用。

## 当前状态分析

### worker/collector 目录情况
- 路径：`/workspace/worker/collector/`
- 内容：仅包含一个空的 `__init__.py` 文件（0 行代码）
- 该目录无任何实际功能代码

### 引用检查结果
经过全项目搜索，**没有任何代码引用 `worker.collector` 或 `worker/collector`**：

| 引用类型 | 结果 |
|---------|------|
| `worker.collector` 导入 | 无匹配 |
| `from worker import collector` | 无匹配 |
| `import worker.collector` | 无匹配 |

### 重要澄清
项目中存在的 `LogCollectorTask`、`DatabaseCollectorTask`、`KafkaCollectorTask` 类位于 `worker/scheduler/tasks/` 目录，**不是** `worker/collector/` 目录：

- `worker/scheduler/tasks/log_collector_task.py` → `LogCollectorTask`
- `worker/scheduler/tasks/database_collector_task.py` → `DatabaseCollectorTask`
- `worker/scheduler/tasks/kafka_collector_task.py` → `KafkaCollectorTask`

`worker/collector/` 是一个完全独立的、空的目录，与上述 Task 类无任何关系。

## Proposed Changes

### 清理操作
1. **删除** `/workspace/worker/collector/` 目录（包含空的 `__init__.py`）

### 无需修改的其他代码
- `worker/scheduler/tasks/` 下的 Task 类保持不变
- `worker/main.py` 保持不变
- `worker/scheduler/tasks/__init__.py` 保持不变

## Assumptions & Decisions
- 确认 `worker/collector/` 为空目录，无实际功能
- 确认清理安全，不影响现有 Task 类

## Verification Steps
1. 确认 `worker/collector/` 目录被删除
2. 运行项目确保无 import 错误：`python -c "from worker.scheduler.tasks import LogCollectorTask, DatabaseCollectorTask, KafkaCollectorTask"`
3. 检查 `worker/main.py` 能否正常加载
