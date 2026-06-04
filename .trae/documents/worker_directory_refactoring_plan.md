# Worker 端目录结构重构计划

## 1. 现状分析

### 当前目录结构
```
worker/
├── adapter/              # 适配器模块
│   ├── __init__.py
│   ├── base.py
│   ├── clickhouse_adapter.py
│   ├── http_adapter.py
│   ├── influxdb_adapter.py
│   ├── redis_adapter.py
│   └── sql_adapter.py
├── collector/            # 日志收集模块
│   ├── __init__.py
│   └── log_collector.py
├── communicator/         # 通信模块
│   ├── __init__.py
│   └── central_client.py
├── core/                 # 核心模块
│   ├── __init__.py
│   ├── auth.py
│   ├── logging.py
│   └── settings.py
├── grpc/                 # gRPC模块
│   ├── __init__.py
│   ├── client.py
│   ├── worker_pb2.py
│   └── worker_pb2_grpc.py
├── metrics/              # 指标转换模块
│   ├── __init__.py
│   └── metric_converter.py
├── scheduler/            # 任务调度模块
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── database_collector_task.py
│   │   ├── log_collector_task.py
│   │   └── metric_converter_task.py
│   ├── __init__.py
│   ├── base_task.py
│   ├── task_scheduler.py
│   └── trade_day_cache.py
├── scripts/              # 脚本目录
│   └── __init__.py
├── transformer/          # 数据转换模块
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── aggregator.py
│   │   ├── filter.py
│   │   ├── formatter.py
│   │   └── json_parser.py
│   ├── __init__.py
│   ├── base.py
│   ├── executor.py
│   ├── loader.py
│   └── registry.py
├── main.py               # 主入口
├── run.sh                # 启动脚本
└── README.md
```

### 存在的问题
1. **结构层次不清晰**：数据采集、处理、调度、通信等层级混杂
2. **模块职责不明确**：adapter、collector、transformer 之间关系不清晰
3. **缺少统一的工具层**：缺少 utils 或 helpers 模块
4. **入口层职责过重**：main.py 中集成了过多功能
5. **缺少测试模块**：没有自己的 tests 目录，依赖项目根目录的 tests

## 2. 重构目标

### 设计原则
1. **单一职责**：每个模块职责清晰
2. **层次分明**：从上到下依次为入口层、调度层、业务层、基础设施层
3. **易于扩展**：方便添加新的适配器、转换任务等
4. **便于测试**：模块解耦，易于单元测试

### 预期结构
```
worker/
├── __init__.py
├── main.py                          # 主入口
├── run.sh                           # 启动脚本
├── README.md
├── config/                          # 配置文件（可选）
│   └── example_config.yaml
│
├── worker/                          # 核心包（新）
│   ├── __init__.py
│   │
│   ├── core/                        # 核心基础设施层
│   │   ├── __init__.py
│   │   ├── settings.py              # 配置管理
│   │   ├── logging.py               # 日志处理
│   │   ├── auth.py                  # 认证工具
│   │   └── exceptions.py            # 自定义异常（新增）
│   │
│   ├── communication/               # 通信层（原 communicator + grpc）
│   │   ├── __init__.py
│   │   ├── central_client.py        # 中心端客户端
│   │   ├── grpc_client.py           # gRPC 客户端（重命名）
│   │   ├── base.py                  # 通信基类（新增）
│   │   └── proto/                   # Protocol Buffer 文件（新增）
│   │       ├── worker.proto
│   │       ├── worker_pb2.py
│   │       └── worker_pb2_grpc.py
│   │
│   ├── scheduler/                   # 任务调度层
│   │   ├── __init__.py
│   │   ├── task_scheduler.py        # 调度器
│   │   ├── base_task.py             # 任务基类
│   │   ├── trade_day_cache.py       # 交易日缓存
│   │   └── tasks/                   # 具体任务实现
│   │       ├── __init__.py
│   │       ├── log_collector_task.py
│   │       ├── metric_converter_task.py
│   │       └── database_collector_task.py
│   │
│   ├── data/                        # 数据处理层（原 collector + adapter + transformer + metrics）
│   │   ├── __init__.py
│   │   │
│   │   ├── collection/              # 数据采集（原 collector）
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # 采集器基类（新增）
│   │   │   └── log_collector.py     # 日志采集器
│   │   │
│   │   ├── adapters/                # 适配器（原 adapter）
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # 适配器基类
│   │   │   ├── sql_adapter.py       # SQL 适配器
│   │   │   ├── clickhouse_adapter.py
│   │   │   ├── redis_adapter.py
│   │   │   ├── http_adapter.py
│   │   │   └── influxdb_adapter.py
│   │   │
│   │   ├── transformation/          # 数据转换（原 transformer）
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # 转换基类
│   │   │   ├── executor.py          # 转换执行器
│   │   │   ├── registry.py          # 任务注册表
│   │   │   ├── loader.py            # 脚本加载器
│   │   │   └── scripts/             # 转换脚本
│   │   │       ├── __init__.py
│   │   │       ├── aggregator.py
│   │   │       ├── filter.py
│   │   │       ├── formatter.py
│   │   │       └── json_parser.py
│   │   │
│   │   └── metrics/                 # 指标处理（原 metrics）
│   │       ├── __init__.py
│   │       ├── base.py              # 指标处理器基类（新增）
│   │       └── metric_converter.py  # 指标转换器
│   │
│   └── utils/                       # 工具层（新增）
│       ├── __init__.py
│       ├── helpers.py               # 通用辅助函数
│       └── constants.py             # 常量定义
│
├── tests/                           # Worker 自身测试（新增）
│   ├── __init__.py
│   ├── test_core/
│   │   ├── __init__.py
│   │   ├── test_settings.py
│   │   ├── test_logging.py
│   │   └── test_auth.py
│   ├── test_communication/
│   │   ├── __init__.py
│   │   └── test_central_client.py
│   ├── test_scheduler/
│   │   ├── __init__.py
│   │   ├── test_task_scheduler.py
│   │   └── test_base_task.py
│   └── test_data/
│       ├── __init__.py
│       ├── test_collection/
│       ├── test_adapters/
│       ├── test_transformation/
│       └── test_metrics/
│
└── scripts/                         # 部署和运维脚本
    └── __init__.py
```

## 3. 详细重构步骤

### 步骤 1：创建新的目录结构
1. 创建 `worker/worker/` 包目录
2. 在新包下创建各子目录：core、communication、scheduler、data、utils、tests
3. 在 data 下创建 collection、adapters、transformation、metrics 子目录

### 步骤 2：移动并重构核心模块
1. 移动 core 模块到新位置
2. 创建 `exceptions.py` 定义自定义异常
3. 更新所有导入路径

### 步骤 3：重构通信层
1. 将 communicator 和 grpc 合并到 communication 目录
2. 创建 communication/base.py 定义通信基类
3. 将 grpc/ 下的 proto 文件移动到 communication/proto/
4. 重命名 grpc/client.py 为 grpc_client.py
5. 更新导入

### 步骤 4：保持调度层基本不变
1. scheduler 目录基本保持原样
2. 更新内部导入路径

### 步骤 5：重构数据处理层
1. 创建 data/collection/ 目录，移动 collector 内容，新增采集器基类
2. 创建 data/adapters/ 目录，移动 adapter 内容
3. 创建 data/transformation/ 目录，移动 transformer 内容
4. 创建 data/metrics/ 目录，移动 metrics 内容，新增指标处理器基类
5. 更新所有相关导入

### 步骤 6：新增工具层
1. 创建 utils/helpers.py 存放通用辅助函数
2. 创建 utils/constants.py 存放常量定义
3. 将散落的工具函数整理到这里

### 步骤 7：新增测试目录
1. 创建 tests/ 目录
2. 按模块组织测试文件
3. 从项目根目录 tests/worker/ 迁移相关测试

### 步骤 8：更新入口文件
1. 重构 main.py，简化其职责
2. 更新所有导入路径
3. 保持功能不变

### 步骤 9：更新文档和脚本
1. 更新 README.md
2. 更新 run.sh
3. 更新 CODE_WIKI.md 中的相关部分

### 步骤 10：验证和测试
1. 运行现有测试确保功能正常
2. 修复所有导入错误
3. 验证 Worker 可以正常启动和运行

## 4. 文件迁移详细列表

### 核心模块
| 原路径 | 新路径 | 备注 |
|--------|--------|------|
| worker/core/settings.py | worker/worker/core/settings.py | 直接移动 |
| worker/core/logging.py | worker/worker/core/logging.py | 直接移动 |
| worker/core/auth.py | worker/worker/core/auth.py | 直接移动 |
| (新增) | worker/worker/core/exceptions.py | 新建 |

### 通信模块
| 原路径 | 新路径 | 备注 |
|--------|--------|------|
| worker/communicator/central_client.py | worker/worker/communication/central_client.py | 直接移动 |
| worker/grpc/client.py | worker/worker/communication/grpc_client.py | 重命名 |
| worker/grpc/worker_pb2.py | worker/worker/communication/proto/worker_pb2.py | 移动 |
| worker/grpc/worker_pb2_grpc.py | worker/worker/communication/proto/worker_pb2_grpc.py | 移动 |
| (新增) | worker/worker/communication/base.py | 新建基类 |

### 调度模块
| 原路径 | 新路径 | 备注 |
|--------|--------|------|
| worker/scheduler/task_scheduler.py | worker/worker/scheduler/task_scheduler.py | 直接移动 |
| worker/scheduler/base_task.py | worker/worker/scheduler/base_task.py | 直接移动 |
| worker/scheduler/trade_day_cache.py | worker/worker/scheduler/trade_day_cache.py | 直接移动 |
| worker/scheduler/tasks/* | worker/worker/scheduler/tasks/* | 直接移动 |

### 数据处理模块 - 采集
| 原路径 | 新路径 | 备注 |
|--------|--------|------|
| worker/collector/log_collector.py | worker/worker/data/collection/log_collector.py | 直接移动 |
| (新增) | worker/worker/data/collection/base.py | 新建基类 |

### 数据处理模块 - 适配器
| 原路径 | 新路径 | 备注 |
|--------|--------|------|
| worker/adapter/base.py | worker/worker/data/adapters/base.py | 直接移动 |
| worker/adapter/sql_adapter.py | worker/worker/data/adapters/sql_adapter.py | 直接移动 |
| worker/adapter/clickhouse_adapter.py | worker/worker/data/adapters/clickhouse_adapter.py | 直接移动 |
| worker/adapter/redis_adapter.py | worker/worker/data/adapters/redis_adapter.py | 直接移动 |
| worker/adapter/http_adapter.py | worker/worker/data/adapters/http_adapter.py | 直接移动 |
| worker/adapter/influxdb_adapter.py | worker/worker/data/adapters/influxdb_adapter.py | 直接移动 |

### 数据处理模块 - 转换
| 原路径 | 新路径 | 备注 |
|--------|--------|------|
| worker/transformer/base.py | worker/worker/data/transformation/base.py | 直接移动 |
| worker/transformer/executor.py | worker/worker/data/transformation/executor.py | 直接移动 |
| worker/transformer/registry.py | worker/worker/data/transformation/registry.py | 直接移动 |
| worker/transformer/loader.py | worker/worker/data/transformation/loader.py | 直接移动 |
| worker/transformer/scripts/* | worker/worker/data/transformation/scripts/* | 直接移动 |

### 数据处理模块 - 指标
| 原路径 | 新路径 | 备注 |
|--------|--------|------|
| worker/metrics/metric_converter.py | worker/worker/data/metrics/metric_converter.py | 直接移动 |
| (新增) | worker/worker/data/metrics/base.py | 新建基类 |

### 工具模块（新增）
| 路径 | 说明 |
|------|------|
| worker/worker/utils/helpers.py | 通用辅助函数 |
| worker/worker/utils/constants.py | 常量定义 |

### 测试模块（新增）
| 路径 | 说明 |
|------|------|
| worker/tests/ | Worker 测试目录 |
| worker/tests/test_core/ | 核心模块测试 |
| worker/tests/test_communication/ | 通信模块测试 |
| worker/tests/test_scheduler/ | 调度模块测试 |
| worker/tests/test_data/ | 数据处理模块测试 |

## 5. 风险和注意事项

### 风险点
1. **导入路径错误**：大量文件移动会导致导入错误，需要仔细检查
2. **测试覆盖**：需要确保所有功能都有测试覆盖
3. **向后兼容**：需要确保与 master 端的通信不受影响

### 注意事项
1. 重构过程中保持 git 历史可追踪
2. 分步骤提交，每步确保功能正常
3. 充分测试后再合并
4. 更新相关文档

## 6. 验收标准

1. 新的目录结构符合预期设计
2. 所有现有测试通过
3. Worker 可以正常启动和运行
4. 与 master 端通信正常
5. 所有功能与重构前保持一致
