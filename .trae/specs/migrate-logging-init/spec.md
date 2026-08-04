# 日志格式初始化迁移 Spec

## Why
当前 `master/main.py` 在模块顶层以散落式内联代码完成日志系统初始化（创建目录、`FileHandler`、`AsyncFileHandler`、`Formatter`、根 logger 配置），与 `AsyncFileHandler` 的定义分别处于不同文件，导致日志初始化逻辑难以复用与测试。将初始化逻辑收敛到 `master/core/logging.py` 中，使 `main.py` 仅负责调用，可提升内聚性并便于后续在其他入口（如 worker、CLI 脚本）复用。

## What Changes
- 在 `master/core/logging.py` 中新增 `setup_logging(settings)` 函数，封装以下现有逻辑：
  - 创建 `settings.log_dir` 所属目录（若不存在）
  - 创建带 `utf-8` 编码的 `FileHandler`，级别取自 `settings.log_level`
  - 用 `AsyncFileHandler` 包装 `FileHandler`
  - 配置日志格式 `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`
  - 配置根 logger（级别、添加 `async_file_handler`）
- 移除 `master/main.py` 中第 94-113 行的内联日志初始化代码，改为在导入 `AsyncFileHandler` 之后调用 `setup_logging(settings)`
- 保持现有行为完全一致：日志级别、日志路径、格式字符串、handler 组合方式均不变

## Impact
- Affected specs: 无
- Affected code:
  - [master/core/logging.py](file:///Users/shun/PythonProject/sretools/master/core/logging.py) — 新增 `setup_logging` 函数
  - [master/main.py](file:///Users/shun/PythonProject/sretools/master/main.py) — 删除内联初始化代码，改为函数调用

## ADDED Requirements
### Requirement: 日志系统初始化函数
`master/core/logging.py` SHALL 提供 `setup_logging(settings)` 函数，封装日志目录创建、`FileHandler`/`AsyncFileHandler` 创建、`Formatter` 配置与根 logger 注册的全部逻辑。

#### Scenario: 正常初始化
- **WHEN** `setup_logging(settings)` 被调用且 `settings.log_dir` 指向的目录尚不存在
- **THEN** 函数创建对应目录，并使用 `utf-8` 编码的 `FileHandler` 包装为 `AsyncFileHandler` 添加到根 logger

#### Scenario: 根 logger 配置
- **WHEN** `setup_logging(settings)` 调用完成
- **THEN** 根 logger 级别等于 `settings.log_level` 对应的 logging 级别常量，且已附加 `async_file_handler`，格式为 `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`

#### Scenario: 可重复调用幂等性
- **WHEN** `setup_logging(settings)` 被多次调用
- **THEN** 不应重复向根 logger 堆叠 handler（避免重复输出），调用方在重复调用前应自行清理或函数内部做去重

## MODIFIED Requirements
### Requirement: master/main.py 启动入口日志初始化
`master/main.py` SHALL 在导入 `AsyncFileHandler` 与 `settings` 之后，通过调用 `master.core.logging.setup_logging(settings)` 完成日志系统初始化，不再保留任何内联的 handler 创建与 formatter 配置代码。`logging`、`FileHandler` 顶层导入若无其他用途应一并移除。

## REMOVED Requirements
无（仅迁移，不删除功能）。
