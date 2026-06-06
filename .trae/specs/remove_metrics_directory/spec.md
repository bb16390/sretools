# 移除 Worker Metrics 目录 - 产品需求文档

## Overview
- **Summary**: 移除 worker/metrics 目录并更新相关引用，因为该模块已迁移到 worker/transformer/scripts/ 下
- **Purpose**: 清理旧的代码目录，避免混淆，确保代码库的一致性
- **Target Users**: 开发团队

## Goals
- 移除 worker/metrics 目录
- 更新项目内对 worker/metrics 的引用
- 更新 CODE_WIKI.md 文档（如需要）
- 确保代码正常运行

## Non-Goals (Out of Scope)
- 不修改 transformer/scripts/metric_converter.py 的功能
- 不修改其他无关代码

## Background & Context
- worker/metrics/metric_converter.py 已迁移到 worker/transformer/scripts/metric_converter.py
- 当前项目中仍有多处引用旧路径
- CODE_WIKI.md 也有相关文档需要更新

## Functional Requirements
- **FR-1**: 移除 worker/metrics 目录
- **FR-2**: 更新 worker/main.py 中对 metrics 模块的引用
- **FR-3**: 更新 worker/scheduler/tasks/metric_converter_task.py 中对 metrics 模块的引用
- **FR-4**: 更新 worker/README.md 文档
- **FR-5**: 更新 CODE_WIKI.md 文档

## Non-Functional Requirements
- **NFR-1**: 确保所有代码修改后无语法错误
- **NFR-2**: 保持代码库的可读性和可维护性

## Constraints
- **Technical**: 代码是 Python 项目
- **Dependencies**: 无外部依赖

## Assumptions
- 迁移后的 transformer/scripts/metric_converter.py 已经是可用的
- 当前对 metrics 模块的引用是旧的实现，需要清理
- 移除旧代码不会影响项目功能

## Acceptance Criteria

### AC-1: metrics 目录已移除
- **Given**: 当前项目中有 worker/metrics 目录
- **When**: 执行删除操作
- **Then**: worker/metrics 目录及其内容完全移除
- **Verification**: programmatic

### AC-2: main.py 引用已更新
- **Given**: worker/main.py 引用 worker.metrics.metric_converter
- **When**: 更新引用
- **Then**: 移除相关导入和初始化代码
- **Verification**: programmatic

### AC-3: metric_converter_task.py 引用已更新
- **Given**: worker/scheduler/tasks/metric_converter_task.py 引用 worker.metrics.metric_converter
- **When**: 更新引用
- **Then**: 根据需要更新导入（或移除，如果不需要）
- **Verification**: programmatic

### AC-4: worker/README.md 已更新
- **Given**: worker/README.md 提到 metrics 目录
- **When**: 更新文档
- **Then**: 文档不再提及旧的 metrics 目录结构
- **Verification**: programmatic

### AC-5: CODE_WIKI.md 已更新（如需要）
- **Given**: CODE_WIKI.md 详细说明了 metrics 模块
- **When**: 检查文档
- **Then**: 更新或移除相关章节
- **Verification**: human-judgment

### AC-6: 代码可以正常运行
- **Given**: 所有修改完成
- **When**: 运行相关测试
- **Then**: 无语法错误，项目可以正常启动
- **Verification**: programmatic

## Open Questions
- 无
