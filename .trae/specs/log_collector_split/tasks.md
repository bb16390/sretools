# LogCollector 功能拆分 - The Implementation Plan (Decomposed and Prioritized Task List)

## [x] Task 1: 更新 LogCollectorTask 集成队列和存储功能
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 将 LogCollector 类中的队列管理功能集成到 LogCollectorTask
  - 将本地存储功能（save_to_local, check_storage_size）也集成到 LogCollectorTask
  - 移除对 LogCollector 类的依赖
- **Acceptance Criteria Addressed**: FR-1, FR-2, FR-3
- **Test Requirements**:
  - `programmatic` TR-1.1: 验证队列能正常添加和获取日志
  - `programmatic` TR-1.2: 验证本地存储功能正常
  - `human-judgement` TR-1.3: 代码审核，确保逻辑正确
- **Notes**: 保持原有功能行为不变

## [ ] Task 2: 创建本地存储工具类（可选，如果需要复用）
- **Priority**: P2
- **Depends On**: None
- **Description**: 
  - 考虑是否需要提取通用的本地存储功能到单独的工具模块
  - 如果需要，创建工具类并在 LogCollectorTask 中使用
- **Acceptance Criteria Addressed**: FR-2
- **Test Requirements**:
  - `human-judgement` TR-2.1: 代码审核，确保结构合理
- **Notes**: 可选任务，根据代码结构决定是否需要

## [x] Task 3: 更新 main.py 移除对 LogCollector 的引用
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 检查 main.py 中对 LogCollector 的引用并移除
  - 确保 Worker 初始化时不再创建 LogCollector 实例
- **Acceptance Criteria Addressed**: FR-5
- **Test Requirements**:
  - `programmatic` TR-3.1: 验证 main.py 能正常导入和运行
- **Notes**: 检查 Worker 类的 __init__ 方法

## [x] Task 4: 检查并更新其他可能的引用
- **Priority**: P1
- **Depends On**: Task 1
- **Description**: 
  - 使用 grep 查找其他可能引用 LogCollector 的地方
  - 更新这些引用以适配新的结构
- **Acceptance Criteria Addressed**: FR-5
- **Test Requirements**:
  - `programmatic` TR-4.1: 搜索项目中是否还有 LogCollector 的引用
- **Notes**: 确保所有引用都已更新

## [x] Task 5: 删除 log_collector.py 文件
- **Priority**: P0
- **Depends On**: Task 1, Task 3, Task 4
- **Description**: 
  - 确认没有任何代码引用 log_collector.py
  - 删除该文件
- **Acceptance Criteria Addressed**: FR-4
- **Test Requirements**:
  - `programmatic` TR-5.1: 验证文件已删除
  - `programmatic` TR-5.2: 验证项目仍能正常运行
- **Notes**: 删除前做最终检查

## [x] Task 6: 验证功能完整性
- **Priority**: P0
- **Depends On**: Task 1-5
- **Description**: 
  - 测试所有功能是否正常
  - 验证日志收集、存储等功能
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-4
- **Test Requirements**:
  - `programmatic` TR-6.1: 功能测试
  - `human-judgement` TR-6.2: 代码结构审查
