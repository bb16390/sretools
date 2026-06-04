# Master-Worker gRPC 通信迁移 - 可行性评估报告

## 概述

本报告评估了将当前 SRE Tools 系统中 master 和 worker 之间的通信方式从 HTTP + WebSocket 完全迁移到 gRPC 的可行性。

### 当前架构
- **通信协议**：HTTP REST API + WebSocket
- **master**：FastAPI 服务，提供 REST API 和 WebSocket 连接
- **worker**：使用 requests 和 websockets 库进行通信

## 目标

1. 评估 gRPC 在当前系统中的适用性
2. 分析迁移的优缺点
3. 提供详细的迁移方案和工作量评估
4. 识别潜在风险和挑战

## 非目标

- 不对 master 或 worker 的内部逻辑进行重构
- 不改变用户与 master 管理后台的交互方式
- 不修改现有的 API 接口（除了通信协议变更）

## 背景与上下文

### 当前通信机制

当前 master-worker 通信分为两类：

1. **单向通信**：worker 到 master（HTTP POST/GET）
   - 注册
   - 心跳
   - 发送日志
   - 发送指标
   - 获取配置
   - 健康检查

2. **双向通信**：master 到 worker（WebSocket）
   - 配置更新
   - 任务更新
   - 交易日数据推送

### 现有代码模块

- **master/worker/routes.py**：定义所有 API 端点和 WebSocket 管理
- **worker/communicator/central_client.py**：实现通信逻辑和故障切换机制

## gRPC 分析

### gRPC 是什么

gRPC 是 Google 开发的高性能远程过程调用框架，基于 HTTP/2 协议和 Protocol Buffers。

### 优势

1. **高性能**：
   - 基于 HTTP/2，支持多路复用
   - 二进制序列化，比 JSON 更高效
   - 更小的消息体积

2. **强类型**：
   - Protocol Buffers 提供强类型定义
   - 编译时类型检查
   - 自动生成客户端和服务端代码

3. **双向流式通信**：
   - 原生支持双向流式通信
   - 可替代 WebSocket 实现实时通信

4. **更好的错误处理**：
   - 标准化的错误码
   - 内置的重试机制

### 劣势

1. **学习曲线**：
   - 需要学习 Protocol Buffers 语法
   - 开发团队需要熟悉 gRPC 概念

2. **调试难度**：
   - 二进制消息，不如 JSON 直观
   - 需要特定工具调试 gRPC 通信

3. **依赖增加**：
   - 需要引入 grpcio 和 grpcio-tools 等依赖
   - 代码生成增加构建步骤

## 功能需求

### FR1：定义 gRPC 服务和消息类型
- 使用 Protocol Buffers 定义所有服务接口
- 包括：注册、心跳、日志、指标、配置、任务管理等

### FR2：实现 gRPC 服务端（master）
- 替代现有的 FastAPI 路由
- 支持流式通信
- 保持现有的安全验证机制

### FR3：实现 gRPC 客户端（worker）
- 替代 requests 和 websockets 库
- 保持现有的故障切换和重连逻辑
- 支持本地缓存

### FR4：迁移现有功能
- 保持所有现有功能不变
- 确保向后兼容性（可选）

## 非功能需求

### NFR1：性能
- 消息延迟不增加
- 吞吐量不降低
- 资源消耗（CPU/内存）可控

### NFR2：可靠性
- 保持现有的故障切换机制
- 支持多个 master 实例
- 优雅降级和本地缓存

### NFR3：可维护性
- 代码结构清晰
- 文档完善
- 易于扩展

## 约束

1. **技术栈**：必须使用 Python
2. **兼容性**：保持现有的配置和数据结构
3. **安全**：保留现有的签名验证机制

## 假设

1. 开发团队愿意学习和接受 gRPC
2. 项目可以接受引入新的依赖
3. 有足够的时间进行测试和验证

## 接受标准

### AC1：功能完整性
- **给定**：所有 gRPC 服务已实现
- **当**：运行现有的测试用例
- **则**：所有测试应该通过
- **验证**：programmatic

### AC2：性能指标
- **给定**：生产级别的负载
- **当**：对比 HTTP 和 gRPC 的性能
- **则**：gRPC 的性能应该优于或等于 HTTP
- **验证**：programmatic

### AC3：可靠性
- **给定**：模拟网络故障
- **当**：master 或 worker 发生故障
- **则**：系统应该能够正确恢复
- **验证**：programmatic

## 开放性问题

1. 是否需要保持向后兼容性（同时支持 HTTP 和 gRPC）？
2. 是否需要对现有数据进行迁移？
3. gRPC 的端口如何规划？

---

## 详细分析报告

### 1. 协议对比

| 特性 | HTTP + WebSocket | gRPC |
|------|------------------|------|
| 序列化 | JSON（文本） | Protocol Buffers（二进制） |
| 传输协议 | HTTP/1.1 + WebSocket | HTTP/2 |
| 多路复用 | 不支持 | 支持 |
| 强类型 | 否 | 是 |
| 双向通信 | WebSocket 支持 | 原生支持 |
| 流式传输 | 需要额外实现 | 原生支持 |
| 代码生成 | 无 | 有 |
| 性能 | 一般 | 高 |
| 调试难度 | 低 | 高 |

### 2. 工作量评估

| 阶段 | 任务 | 预计工作量（人天） |
|------|------|-------------------|
| 准备 | 学习 gRPC 和 Protocol Buffers | 3 |
| 设计 | 设计服务接口和消息类型 | 2 |
| 实现 | 实现 gRPC 服务端（master） | 5 |
| 实现 | 实现 gRPC 客户端（worker） | 5 |
| 测试 | 单元测试和集成测试 | 4 |
| 文档 | 编写文档 | 2 |
| **总计** | | **21** |

### 3. 风险与挑战

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 学习曲线 | 中 | 高 | 提前培训，分阶段实施 |
| 调试困难 | 高 | 中 | 引入调试工具，保留日志 |
| 性能问题 | 高 | 低 | 充分性能测试 |
| 依赖冲突 | 中 | 低 | 仔细评估依赖版本 |
| 向后兼容性 | 中 | 中 | 考虑同时支持两种协议 |

### 4. 迁移策略

#### 策略 A：完全替换（推荐）
- 优点：架构清晰，维护成本低
- 缺点：风险较高，需要全面测试
- 适用场景：开发资源充足，测试覆盖完善

#### 策略 B：渐进式迁移
- 第一阶段：同时支持 HTTP 和 gRPC
- 第二阶段：逐步将 worker 迁移到 gRPC
- 第三阶段：移除 HTTP 支持
- 优点：风险低，可以逐步验证
- 缺点：维护成本高，代码复杂

#### 策略 C：混合方案
- 关键功能使用 gRPC，其他功能保留 HTTP
- 优点：平衡风险和收益
- 缺点：架构不一致

### 5. 技术方案

#### 5.1 Protocol Buffers 定义示例

```protobuf
syntax = "proto3";

package worker;

service WorkerService {
  // 注册 worker
  rpc RegisterWorker(RegisterRequest) returns (RegisterResponse);
  
  // 发送心跳
  rpc SendHeartbeat(HeartbeatRequest) returns (HeartbeatResponse);
  
  // 发送日志（流式）
  rpc SendLogs(stream LogEntry) returns (SendLogsResponse);
  
  // 发送指标（流式）
  rpc SendMetrics(stream MetricEntry) returns (SendMetricsResponse);
  
  // 获取配置
  rpc GetConfig(GetConfigRequest) returns (GetConfigResponse);
  
  // 双向流式通信（替代 WebSocket）
  rpc Communicate(stream WorkerMessage) returns (stream MasterMessage);
}

message RegisterRequest {
  string worker_id = 1;
  WorkerInfo info = 2;
  string signature = 3;
}

message WorkerInfo {
  string version = 1;
  string host = 2;
  int32 port = 3;
  double timestamp = 4;
}

// ... 其他消息定义
```

#### 5.2 Master 端实现要点

1. 使用 `grpcio` 库创建 gRPC 服务
2. 与 FastAPI 服务并行运行（或替换）
3. 保留现有的签名验证逻辑
4. 实现连接管理（替代 WebSocket 管理器）

#### 5.3 Worker 端实现要点

1. 使用生成的 gRPC 客户端代码
2. 保留故障切换和重连逻辑
3. 实现流式通信
4. 保持本地缓存功能

### 6. 推荐方案

基于分析，我们推荐：

1. **采用策略 B（渐进式迁移）**
   - 降低风险
   - 可以分阶段验证
   - 便于回滚

2. **先迁移非关键功能**
   - 心跳
   - 健康检查
   - 获取配置

3. **再迁移关键功能**
   - 日志和指标发送
   - 双向通信

4. **最后移除 HTTP 支持**
   - 确认 gRPC 稳定后
   - 清理旧代码

### 7. 下一步行动

1. 确认开放性问题的答案
2. 制定详细的迁移计划
3. 搭建 gRPC 开发环境
4. 进行概念验证（POC）

---

## 结论

将 master-worker 通信迁移到 gRPC 在技术上是可行的，并且具有显著的优势，包括更好的性能、强类型支持和原生的双向流式通信。然而，这也需要一定的学习成本和开发工作量。我们建议采用渐进式迁移策略，以降低风险并逐步验证方案的有效性。
