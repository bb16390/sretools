# Kafka 适配器 - 实现计划

## [x] 任务 1: 添加 confluent-kafka 依赖
- **优先级**: P0
- **依赖**: None
- **描述**: 
  - 在 pyproject.toml 中添加 confluent-kafka 库依赖
  - 使用 uv 安装新依赖
- **验收标准对应**: FR-1
- **测试要求**:
  - programmatic: 验证 uv sync 成功，confluent-kafka 库可正确导入
- **备注**: 检查项目的 Python 版本兼容性

## [x] 任务 2: 实现 Kafka 适配器 (KafkaAdapter)
- **优先级**: P0
- **依赖**: 任务 1
- **描述**: 
  - 在 /workspace/worker/adapter/ 目录下创建 kafka_adapter.py
  - 继承 AsyncBaseAdapter
  - 实现 Kafka 消费者的初始化、连接和关闭
  - 支持配置 Kafka 集群地址、主题、消费者组、偏移量重置策略等
  - 实现 consume 方法用于消费消息
  - 实现 commit_offset 方法用于提交偏移量
- **验收标准对应**: FR-1
- **测试要求**:
  - programmatic: 单元测试验证适配器初始化、连接、消费和关闭
  - human-judgement: 代码审核，确保架构一致性
- **备注**: 参考现有适配器（如 RedisAdapter）的实现风格

## [x] 任务 3: 更新适配器注册表
- **优先级**: P1
- **依赖**: 任务 2
- **描述**: 
  - 在 /workspace/worker/adapter/__init__.py 中添加 KafkaAdapter 的导入和导出
  - 更新 database_collector_task.py 中的 _ADAPTER_CLASS_MAP，添加 "kafka" 映射
- **验收标准对应**: FR-1, FR-2
- **测试要求**:
  - programmatic: 验证适配器可通过 AdapterManager 正确获取
- **备注**: 保持与其他适配器相同的注册方式

## [x] 任务 4: 实现 Kafka 收集任务 (KafkaCollectorTask)
- **优先级**: P0
- **依赖**: 任务 2, 3
- **描述**: 
  - 在 /workspace/worker/scheduler/tasks/ 目录下创建 kafka_collector_task.py
  - 继承 BaseTask
  - 实现 _run 方法，包含消费循环
  - 集成 TransformExecutor 进行消息转换
  - 使用 _notify_status 上报处理结果
- **验收标准对应**: FR-2, FR-5, FR-6
- **测试要求**:
  - programmatic: 单元测试验证任务初始化、运行、停止
  - human-judgement: 代码审核
- **备注**: 参考 DatabaseCollectorTask 的实现模式

## [x] 任务 5: 实现消费进度持久化
- **优先级**: P0
- **依赖**: 任务 2, 4
- **描述**: 
  - 实现 OffsetManager 类，用于管理和持久化消费偏移量
  - 支持两种存储方式：Redis (优先) 和本地文件系统
  - 在 KafkaCollectorTask 中集成 OffsetManager
  - 实现定期保存偏移量的机制
- **验收标准对应**: FR-3, FR-4
- **测试要求**:
  - programmatic: 单元测试验证偏移量保存、读取和恢复
- **备注**: 偏移量存储 key 可包含任务 ID、主题和分区信息

## [x] 任务 6: 注册新任务类型
- **优先级**: P1
- **依赖**: 任务 4, 5
- **描述**: 
  - 在 /workspace/worker/scheduler/tasks/__init__.py 中导出 KafkaCollectorTask
  - 在 /workspace/worker/main.py 中注册 "kafka_collector" 任务类型
- **验收标准对应**: FR-2
- **测试要求**:
  - programmatic: 验证任务调度器可正确创建和启动 KafkaCollectorTask
- **备注**: 保持与其他任务相同的注册方式

## [x] 任务 7: 集成测试和验证
- **优先级**: P1
- **依赖**: 任务 1-6
- **描述**: 
  - 编写集成测试，验证完整的消费流程
  - 验证任务重启后不重复消费
  - 验证消费进度上报功能
- **验收标准对应**: AC-1 到 AC-5
- **测试要求**:
  - programmatic: 集成测试验证所有功能
  - human-judgement: 功能测试和性能测试
- **备注**: 可使用测试 Kafka 集群或 mock 对象
