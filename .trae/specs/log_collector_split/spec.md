# LogCollector 功能拆分 - Product Requirement Document

## Overview
- **Summary**: 将现有的 log_collector.py 文件中的功能进行拆分，分别集成到 log_collector_task.py 和 kafka_adapter.py 中，最终删除 log_collector.py 文件，使代码结构更加清晰和模块化。
- **Purpose**: 重构代码架构，将日志收集的任务逻辑和数据处理逻辑分离，提高代码的可维护性和可扩展性。
- **Target Users**: 开发者和维护者，需要对日志收集功能进行理解和扩展。

## Goals
- 将 LogCollector 类中的队列管理功能集成到 LogCollectorTask
- 将本地存储功能集成到合适的模块（任务或适配器）
- 保持现有功能的完整性和兼容性
- 删除 log_collector.py 文件
- 确保代码结构更加清晰和模块化

## Non-Goals (Out of Scope)
- 不改变现有功能的业务逻辑
- 不新增功能特性
- 不重构其他模块的代码

## Background & Context
当前项目中，log_collector.py 包含了 LogCollector 类，负责日志队列管理、本地存储等功能，并被 log_collector_task.py 调用。为了架构更清晰，需要将这些功能拆分开来，分别放到任务模块和适配器模块中。

## Functional Requirements
- **FR-1**: 日志队列管理功能迁移到 LogCollectorTask
- **FR-2**: 本地存储功能（保存日志到文件、存储大小管理）迁移到适当位置
- **FR-3**: 更新 log_collector_task.py 以集成这些功能
- **FR-4**: 删除 log_collector.py 文件
- **FR-5**: 确保现有引用 LogCollector 的代码能正常工作

## Non-Functional Requirements
- **NFR-1**: 保持现有功能行为不变
- **NFR-2**: 代码结构清晰，职责分明
- **NFR-3**: 保持良好的代码风格，遵循现有规范

## Constraints
- **Technical**: Python 3.12+，使用现有的项目架构
- **Business**: 保持现有功能正常运行
- **Dependencies**: 不引入新的外部依赖

## Assumptions
- 现有功能测试覆盖足够，重构后可以正常工作
- 用户已了解架构变化，可能需要相应更新调用代码（如果有）

## Acceptance Criteria

### AC-1: LogCollectorTask 集成队列功能
- **Given**: LogCollectorTask 已更新
- **When**: 任务启动时
- **Then**: 任务内部有日志队列管理功能
- **Verification**: `programmatic`
- **Notes**: 验证队列可以正常添加和获取日志

### AC-2: 本地存储功能正常工作
- **Given**: 本地存储功能已迁移
- **When**: 有日志需要存储时
- **Then**: 日志能正常保存到文件，存储大小管理正常
- **Verification**: `programmatic`
- **Notes**: 验证文件写入和旧文件清理功能

### AC-3: log_collector.py 已删除
- **Given**: 功能迁移完成
- **When**: 检查文件系统
- **Then**: log_collector.py 文件已被删除
- **Verification**: `programmatic`

### AC-4: 现有调用保持兼容
- **Given**: 代码重构完成
- **When**: 运行现有功能
- **Then**: 功能正常运行，无错误
- **Verification**: `programmatic`
- **Notes**: 验证 main.py 和其他引用处能正常工作

## Open Questions
- 无
