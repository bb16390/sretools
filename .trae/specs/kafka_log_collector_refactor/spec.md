# Kafka 日志收集器重构 - 产品需求文档

## Overview
- **Summary**: 重构 Worker 端的 log_collector.py，使用 confluent-kafka 库创建 Kafka 适配器，并实现 Kafka 消费进度的记录与上报到 Master 端，避免重复消费 Kafka 消息。
- **Purpose**: 提供可靠的 Kafka 消息消费机制，确保消息不被重复消费，并支持消费进度的持久化与同步。
- **Target Users**: SRE 工程师、系统运维人员。

## Goals
1. 创建基于 confluent-kafka 的 Kafka 适配器，遵循现有 AsyncBaseAdapter 抽象模式
2. 重构 log_collector.py，使用新的 Kafka 适配器消费消息
3. 实现 Kafka 消费进度的本地持久化
4. 实现消费进度上报到 Master 端
5. 支持从本地或 Master 端恢复消费进度，避免重复消费

## Non-Goals (Out of Scope)
- 重写整个 Worker 架构
- 修改现有适配器（Redis、HTTP、InfluxDB 等）的核心逻辑
- 实现消息生产功能（仅消费）

## Background & Context
当前 log_collector.py 使用模拟收集方式，没有实际的外部数据源集成。项目已经有适配器模式（AsyncBaseAdapter）和与 Master 端通信的基础设施（CentralClient）。我们需要：
- 遵循现有适配器模式创建 Kafka 适配器
- 扩展 settings.py 添加 Kafka 相关配置
- 扩展 Master 端 API 接收和存储消费进度
- 确保消费进度的可靠性和一致性

## Functional Requirements
- **FR-1**: Kafka 适配器应支持基本的消费者操作：订阅主题、消费消息、提交偏移量
- **FR-2**: LogCollector 应能从 Kafka 主题消费消息并处理
- **FR-3**: 消费进度（偏移量）应持久化到本地存储
- **FR-4**: 消费进度应定期上报到 Master 端
- **FR-5**: 启动时应能从本地或 Master 端恢复消费进度
- **FR-6**: Master 端应提供 API 接收和存储消费进度

## Non-Functional Requirements
- **NFR-1**: 消费进度上报间隔应可配置（默认 30 秒）
- **NFR-2**: Kafka 连接参数应完全可配置
- **NFR-3**: 本地存储的消费进度文件应具有容错性
- **NFR-4**: 代码应遵循现有项目风格和架构模式

## Constraints
- **Technical**: 使用 confluent-kafka 库，遵循现有适配器模式
- **Business**: 保持与现有 Master-Worker 通信协议兼容
- **Dependencies**: 新增 confluent-kafka 依赖

## Assumptions
1. Kafka 服务端已部署并可访问
2. Master 端有足够的存储空间存储消费进度
3. Worker 与 Master 端的通信是可靠的

## Acceptance Criteria

### AC-1: Kafka 适配器基本功能
- **Given**: 已配置 Kafka 连接参数
- **When**: 初始化 Kafka 适配器并尝试连接
- **Then**: 适配器应能成功连接到 Kafka 集群
- **Verification**: programmatic
- **Notes**: 使用测试 Kafka 集群验证

### AC-2: 消费消息功能
- **Given**: Kafka 适配器已连接并订阅主题
- **When**: 主题中有新消息
- **Then**: 适配器应能成功消费消息
- **Verification**: programmatic

### AC-3: 本地消费进度持久化
- **Given**: LogCollector 正在消费消息
- **When**: 提交消费进度
- **Then**: 进度应保存到本地文件
- **Verification**: programmatic

### AC-4: 消费进度上报到 Master
- **Given**: 消费进度有更新
- **When**: 达到上报间隔
- **Then**: 进度应成功上报到 Master 端
- **Verification**: programmatic

### AC-5: 消费进度恢复
- **Given**: LogCollector 重新启动
- **When**: 初始化时
- **Then**: 应从本地或 Master 恢复上次的消费进度
- **Verification**: programmatic

### AC-6: Master 端接收消费进度
- **Given**: Worker 发送消费进度上报请求
- **When**: Master 端接收请求
- **Then**: 应验证请求并存储消费进度
- **Verification**: programmatic

## Open Questions
- [ ] 消费进度在 Master 端是否需要持久化到数据库还是仅在内存存储？（当前实现使用内存存储，可后续优化）
