# 删除 worker/metrics 目录 - The Implementation Plan (Decomposed and Prioritized Task List)

## [x] Task 1: 检查并移除 worker/main.py 中对 metrics 模块的引用
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 移除 worker/main.py 中对 MetricConverter 的导入
  - 移除 worker/main.py 中对 MetricConverterTask 的导入和注册
  - 移除 worker/main.py 中对 MetricConverter 的初始化代码
- **Acceptance Criteria Addressed**: [AC-2]
- **Test Requirements**:
  - `programmatic` TR-1.1: worker/main.py 中不再有 `from worker.metrics` 或 `MetricConverter` 相关代码
- **Notes**: 保留其他任务类型的注册

## [x] Task 2: 删除 MetricConverterTask 文件及相关引用
- **Priority**: P0
- **Depends On**: [Task 1]
- **Description**: 
  - 删除 /workspace/worker/scheduler/tasks/metric_converter_task.py 文件
  - 更新 /workspace/worker/scheduler/tasks/__init__.py 移除该任务的导出
- **Acceptance Criteria Addressed**: [AC-3]
- **Test Requirements**:
  - `programmatic` TR-2.1: metric_converter_task.py 文件被删除
  - `programmatic` TR-2.2: tasks/__init__.py 中不再有 MetricConverterTask 的导出

## [x] Task 3: 删除 worker/metrics 目录及其内容
- **Priority**: P0
- **Depends On**: [Task 1, Task 2]
- **Description**: 
  - 删除 /workspace/worker/metrics 目录及其所有文件
- **Acceptance Criteria Addressed**: [AC-1]
- **Test Requirements**:
  - `programmatic` TR-3.1: /workspace/worker/metrics 目录完全被删除

## [x] Task 4: 检查并清理其他文件中的 metrics 引用
- **Priority**: P1
- **Depends On**: [Task 3]
- **Description**: 
  - 检查项目中其他可能引用 metrics 模块的文件
  - 清理相关引用
- **Acceptance Criteria Addressed**: [AC-2, AC-3]
- **Test Requirements**:
  - `programmatic` TR-4.1: 项目中不再有对 worker.metrics 的引用

## [x] Task 5: 更新 README 等文档
- **Priority**: P2
- **Depends On**: [Task 4]
- **Description**: 
  - 更新 worker/README.md，移除对 metrics 模块的描述
- **Acceptance Criteria Addressed**: [AC-2, AC-3]
- **Test Requirements**:
  - `human-judgement` TR-5.1: README 文档已更新，不再包含 metrics 模块的描述

## [x] Task 6: 验证项目可以正常启动
- **Priority**: P0
- **Depends On**: [Task 5]
- **Description**: 
  - 验证项目可以正常启动
  - 确保没有导入错误
- **Acceptance Criteria Addressed**: [AC-4]
- **Test Requirements**:
  - `programmatic` TR-6.1: 项目可以正常导入，没有 ImportError
