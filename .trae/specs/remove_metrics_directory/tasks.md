# 移除 Worker Metrics 目录 - 实施任务分解

## [x] Task 1: 更新 worker/main.py
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 移除对 worker.metrics.metric_converter 的导入
  - 移除对 MetricConverter 的初始化代码
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic`: 检查 main.py 无语法错误
- **Notes**: 第 9 行的导入和第 86 行的初始化需要移除

## [x] Task 2: 更新 worker/scheduler/tasks/metric_converter_task.py
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 更新或移除对 worker.metrics.metric_converter 的引用
  - 根据需要调整任务实现
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `programmatic`: 检查 metric_converter_task.py 无语法错误
- **Notes**: 第 6 行导入需要更新

## [x] Task 3: 更新 worker/README.md
- **Priority**: P1
- **Depends On**: None
- **Description**: 
  - 移除文档中对 metrics 目录的引用
  - 更新目录结构说明
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `programmatic`: 检查文档内容已更新

## [x] Task 4: 更新 CODE_WIKI.md
- **Priority**: P1
- **Depends On**: None
- **Description**: 
  - 移除或更新对 worker/metrics 模块的文档说明
  - 更新相关的目录结构和模块说明
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `human-judgment`: 检查文档内容是否需要更新并完成更新

## [x] Task 5: 删除 worker/metrics 目录
- **Priority**: P0
- **Depends On**: Task 1, Task 2, Task 3, Task 4
- **Description**: 
  - 彻底删除 worker/metrics 目录及其所有内容
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `programmatic`: 确认 worker/metrics 目录已不存在

## [x] Task 6: 验证代码运行正常
- **Priority**: P0
- **Depends On**: Task 5
- **Description**: 
  - 运行语法检查确保无错误
  - 确认项目可以正常启动（可选）
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `programmatic`: 运行代码语法检查
