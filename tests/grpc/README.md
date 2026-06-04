# gRPC 测试 - Master-Worker 迁移

此目录包含 Master-Worker 通信从 HTTP + WebSocket 迁移到 gRPC 的相关测试。

## 文件清单

| 文件 | 描述 |
|------|------|
| [`__init__.py`](__init__.py) | gRPC 测试模块初始化 |
| [`test_grpc_complete.py`](test_grpc_complete.py) | 完整的 gRPC 测试（使用 grpc_impl 模块） |
| [`test_grpc_integration.py`](test_grpc_integration.py) | 完整的 gRPC 集成测试（使用项目中的 master/grpc 和 worker/grpc） |
| [`README.md`](README.md) | 本说明文件 |

## 快速开始

### 运行完整测试

```bash
# 方式 1: 使用 grpc_impl 模块（推荐，因为是完全独立的）
cd /workspace
uv run python tests/grpc/test_grpc_complete.py

# 方式 2: 使用集成测试（需要正确的导入配置）
cd /workspace
uv run python tests/grpc/test_grpc_integration.py
```

### 或者使用 grpc_impl 下的测试（更稳定）

```bash
cd /workspace/grpc_impl
uv run python test_grpc.py
```

## 测试内容

这些测试验证了：
- Protocol Buffers 定义的正确性
- gRPC 服务端的正常启动和响应
- gRPC 客户端的连接和通信
- 单向 RPC（注册、心跳、配置、健康检查）
- 客户端流式传输（日志、指标发送）
- 双向流式传输（用于替代 WebSocket）

## 迁移指南

完整的迁移计划和可行性评估，请参阅：
- [`GRPC_MIGRATION_FINAL_REPORT.md`](../../GRPC_MIGRATION_FINAL_REPORT.md) - 最终评估报告
- [`COMPLETE_GUIDE.md`](../../COMPLETE_GUIDE.md) - 完整实施指南
- [`.trae/specs/grpc-migration-feasibility/`](../../.trae/specs/grpc-migration-feasibility/) - 规范文档
