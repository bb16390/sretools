# Master-Worker gRPC 集成使用指南

## 📋 概述

本指南说明如何将 gRPC 集成到现有的 Master-Worker 系统中，支持与 HTTP 服务并行工作。

## 🎯 主要特性

1. **并行工作模式**：gRPC 服务与 HTTP 服务可同时运行
2. **渐进式迁移**：可逐步从 HTTP 迁移到 gRPC
3. **灵活配置**：可配置使用 gRPC、HTTP 或两者同时使用

## 📁 项目结构

### gRPC 相关文件位置

| 组件 | 路径 | 说明 |
|------|------|------|
| **Master gRPC 服务 | `/workspace/master/grpc/server.py` | Master 端的 gRPC 服务实现 |
| **Worker gRPC 客户端** | `/workspace/worker/grpc/client.py` | Worker 端的 gRPC 客户端实现 |
| **Proto 定义** | `/workspace/protos/worker.proto` | Protocol Buffers 服务接口定义 |
| **完整独立实现** | `/workspace/grpc_impl/` | 完全独立的 gRPC 实现（用于测试） |
| **测试文件** | `/workspace/tests/grpc/` | gRPC 相关测试 |

## 🚀 快速开始

### 方式 1：使用完整独立实现（推荐用于测试）

这是最简单的测试方式，使用完全独立的实现进行测试。

```bash
cd /workspace/grpc_impl
uv run python test_grpc.py
```

### 方式 2：在 Master 中启动 gRPC 服务

1. 确保 gRPC 服务已集成到 Master 的 `master/main.py` 中，默认会自动尝试启动。

如果需要单独测试，可以通过以下步骤：

```bash
cd /workspace/grpc_impl
uv run python server.py  # 启动 Master gRPC 服务端
```

然后在另一个终端：

```bash
cd /workspace/grpc_impl
uv run python client.py  # 启动 Worker gRPC 客户端
```

## ⚙️ 配置说明

### Master 端配置

在 Master 中，gRPC 服务已集成到 `master/main.py` 中，默认会自动启动（如果模块可用）。

默认 gRPC 服务默认监听端口：`50051`

### Worker 端配置

编辑 `worker/core/settings.py` 中的 gRPC 配置选项：

```python
# gRPC 配置
grpc_enabled: bool = False  # 是否启用 gRPC
grpc_server_address: str = "localhost:50051"  # gRPC 服务地址
grpc_only: bool = False  # 是否只使用 gRPC（禁用 HTTP）
```

## 📊 功能说明

### 支持的 gRPC 服务

| 服务 | 说明 | 类型 |
|------|------|
| `RegisterWorker` | 注册 Worker | 单向 RPC |
| `SendHeartbeat` | 发送心跳 | 单向 RPC |
| `SendLogs` | 发送日志 | 客户端流式 RPC |
| `SendMetrics` | 发送指标 | 客户端流式 RPC |
| `GetConfig` | 获取配置 | 单向 RPC |
| `HealthCheck` | 健康检查 | 单向 RPC |
| `Communicate` | 双向通信 | 双向流式 RPC（替代 WebSocket） |

### 性能优势

与 HTTP+JSON 相比：
- **序列化速度**：快 3-10 倍
- **消息体积**：小 3-10 倍
- **类型安全**：编译时检查
- **原生流式传输**：支持多种传输

## 📝 测试验证

### 运行完整集成测试

```bash
cd /workspace/tests/grpc
uv run python test_grpc_complete.py  # 使用独立实现测试
# 或者
uv run python test_grpc_integration.py  # 使用项目内集成测试
```

或者使用更稳定的独立实现：

```bash
cd /workspace/grpc_impl
uv run python test_grpc.py
```

### 运行结果应该显示：
- ✅ Protocol Buffers 工作正常
- ✅ gRPC 服务端运行正常
- ✅ gRPC 客户端连接正常
- ✅ 所有 RPC 功能正常
- ✅ 流式传输工作正常

## 🎯 迁移策略

### 阶段 1：并行运行（推荐）
保持 HTTP 和 gRPC 同时启用，Worker 可以逐步迁移。

### 阶段 2：部分迁移
将非关键功能（心跳、健康检查）先迁移到 gRPC。

### 阶段 3：全面迁移
所有功能迁移到 gRPC，HTTP 服务保持作为备份。

## 🔧 常见问题

### gRPC 服务无法启动
检查是否有 `grpcio` 和 `grpcio-tools` 依赖是否正确安装。

### 导入问题
确保路径问题请检查 `sys.path` 是否包含正确的模块导入路径。

## 📚 相关文档

- [`GRPC_MIGRATION_FINAL_REPORT.md`](./GRPC_MIGRATION_FINAL_REPORT.md) - 最终可行性评估报告
- [`COMPLETE_GUIDE.md`](./COMPLETE_GUIDE.md) - 完整实施指南
- [`tests/grpc/README.md`](./tests/grpc/README.md) - 测试使用说明

## ✅ 完成状态

| 项目 | 状态 |
|------|------|
| 可行性评估 | ✅ 完成 |
| gRPC 服务实现 | ✅ 完成 |
| gRPC 客户端实现 | ✅ 完成 |
| Master 端集成 | ✅ 完成 |
| Worker 端配置 | ✅ 完成 |
| 测试用例 | ✅ 完成 |
| 独立完整实现 | ✅ 完成 |
