# Kafka 日志收集器重构 - 实施计划

## [ ] 任务 1: 添加 confluent-kafka 依赖
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 在 pyproject.toml 中添加 confluent-kafka 依赖
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `programmatic`: 运行 `uv sync` 成功安装依赖
- **Notes**: 版本建议使用最新稳定版

## [ ] 任务 2: 创建 Kafka 适配器
- **Priority**: P0
- **Depends On**: 任务 1
- **Description**: 
  - 在 worker/adapter/ 目录下创建 kafka_adapter.py
  - 继承 AsyncBaseAdapter
  - 实现 Kafka 消费者的基本功能：连接、订阅、消费、提交偏移量
- **Acceptance Criteria Addressed**: AC-1, AC-2
- **Test Requirements**:
  - `programmatic`: 能成功初始化适配器并连接到测试 Kafka
  - `programmatic`: 能订阅主题并消费消息
- **Notes**: 支持配置 brokers、group_id、topics 等参数

## [ ] 任务 3: 更新 settings.py 添加 Kafka 配置
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 添加 Kafka 相关配置项（brokers、group_id、topics、consumer_config 等）
  - 添加消费进度上报间隔配置
- **Acceptance Criteria Addressed**: NFR-2
- **Test Requirements**:
  - `programmatic`: 配置项能正确加载和访问
- **Notes**: 保持配置的向后兼容性

## [ ] 任务 4: 重构 log_collector.py
- **Priority**: P0
- **Depends On**: 任务 2, 任务 3
- **Description**: 
  - 重构 LogCollector 类
  - 集成 Kafka 适配器
  - 实现消息处理逻辑
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic`: LogCollector 能成功启动并消费 Kafka 消息
- **Notes**: 保持现有接口的兼容性

## [ ] 任务 5: 实现本地消费进度持久化
- **Priority**: P0
- **Depends On**: 任务 4
- **Description**: 
  - 实现消费进度保存到本地文件的功能
  - 实现从本地文件恢复消费进度的功能
- **Acceptance Criteria Addressed**: AC-3, AC-5
- **Test Requirements**:
  - `programmatic`: 消费进度能正确保存和读取
  - `programmatic`: 重启后能恢复到上次的消费位置
- **Notes**: 文件格式建议使用 JSON

## [ ] 任务 6: 更新 Master 端接收消费进度
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 在 master/worker/routes.py 中添加接收消费进度的 API 端点
  - 实现消费进度的存储（内存存储，后续可优化到数据库）
  - 添加获取消费进度的 API 端点
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `programmatic`: API 能成功接收和返回消费进度
- **Notes**: 遵循现有的签名验证机制

## [ ] 任务 7: 实现消费进度上报到 Master
- **Priority**: P0
- **Depends On**: 任务 5, 任务 6
- **Description**: 
  - 在 CentralClient 中添加上报消费进度的方法
  - 在 LogCollector 中集成进度上报功能
  - 实现从 Master 端恢复消费进度的功能
- **Acceptance Criteria Addressed**: AC-4, AC-5
- **Test Requirements**:
  - `programmatic`: 消费进度能成功上报到 Master
  - `programmatic`: 能从 Master 端获取并恢复消费进度
- **Notes**: 上报间隔可配置

## [ ] 任务 8: 更新 LogCollectorTask
- **Priority**: P1
- **Depends On**: 任务 7
- **Description**: 
  - 更新 LogCollectorTask 以使用重构后的 LogCollector
  - 确保任务能正确启动、停止和暂停
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic`: LogCollectorTask 能正常运行
- **Notes**: 保持任务接口的兼容性

## [ ] 任务 9: 集成测试和验证
- **Priority**: P1
- **Depends On**: 任务 8
- **Description**: 
  - 端到端测试整个流程
  - 验证消费进度的持久化和恢复
  - 验证与 Master 端的通信
- **Acceptance Criteria Addressed**: AC-1 到 AC-6
- **Test Requirements**:
  - `programmatic`: 所有功能正常工作
  - `human-judgement`: 代码审查通过，架构合理
- **Notes**: 模拟各种异常场景测试
