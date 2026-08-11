# 统一 Master 日志配置 Spec

## Why
当前 master 的日志配置分散在多处：日志格式字符串硬编码在 `master/core/logging.py` 中，而 `scripts/start.sh` 又单独定义了 `LOG_DIR`/`MASTER_LOG` 路径用于 stdout/stderr 重定向（`$PROJECT_ROOT/logs/master.log`），与 `settings.log_dir`（`$MASTER_DIR/log/uvicorn.log`）不一致。导致通过脚本启动和直接启动 `master/main.py` 时，日志写入位置和配置来源不统一，难以维护。

## What Changes
- 在 `master/core/settings.py` 中新增 `log_format` 字段，将日志格式字符串从 `logging.py` 提取到 settings 中
- 修改 `master/core/logging.py` 的 `setup_logging`，使用 `settings.log_format` 替代硬编码的格式字符串
- 修改 `scripts/start.sh`，移除 master 专用的 `LOG_DIR`/`MASTER_LOG` 硬编码路径，改为从 `master/core/settings.py` 读取 `settings.log_dir` 作为 stdout/stderr 重定向目标
- 修改 `scripts/stop.sh`，状态展示时使用与 settings 一致的 master 日志路径
- worker 的日志路径保持不变（不在本次变更范围）

## Impact
- Affected specs:
  - [migrate-logging-init](file:///workspace/.trae/specs/migrate-logging-init/spec.md) — 本次在此基础上进一步将格式配置收敛到 settings
  - [project-scripts](file:///workspace/.trae/specs/project-scripts/spec.md) — 脚本日志路径来源变更为 settings.py
- Affected code:
  - [master/core/settings.py](file:///workspace/master/core/settings.py) — 新增 `log_format` 字段
  - [master/core/logging.py](file:///workspace/master/core/logging.py) — `setup_logging` 使用 `settings.log_format`
  - [scripts/start.sh](file:///workspace/scripts/start.sh) — master 日志路径从 settings.py 读取
  - [scripts/stop.sh](file:///workspace/scripts/stop.sh) — 状态展示使用 settings.py 中的路径

## ADDED Requirements

### Requirement: 日志格式配置项
`master/core/settings.py` SHALL 提供 `log_format` 字段，作为日志格式的唯一配置来源，默认值为 `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`。

#### Scenario: 格式字段存在
- **WHEN** 读取 `settings.log_format`
- **THEN** 返回非空字符串，默认为 `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`

### Requirement: 脚本读取 master 日志路径
`scripts/start.sh` SHALL 通过调用 Python 从 `master.core.settings` 读取 `settings.log_dir`，作为 master 服务 stdout/stderr 的重定向目标，不再使用脚本内硬编码的 `$PROJECT_ROOT/logs/master.log`。

#### Scenario: 正常读取日志路径
- **WHEN** `start.sh` 准备启动 master 服务且 Python 环境可用
- **THEN** 脚本通过 `python -c "from master.core.settings import settings; print(settings.log_dir)"` 获取日志文件路径，并将其用于 `nohup` 的 stdout/stderr 重定向

#### Scenario: Python 不可用时回退
- **WHEN** Python 环境不可用或读取 settings 失败
- **THEN** 脚本回退到 `$MASTER_DIR/log/uvicorn.log` 作为日志路径，并继续执行

### Requirement: 脚本创建日志目录
`scripts/start.sh` SHALL 在重定向 stdout/stderr 之前，根据从 settings 读取的日志路径创建其父目录。

#### Scenario: 日志目录不存在
- **WHEN** settings.log_dir 的父目录不存在
- **THEN** 脚本通过 `mkdir -p` 创建该目录后再进行重定向

## MODIFIED Requirements

### Requirement: master/core/logging.py setup_logging 使用 settings.log_format
`master/core/logging.py` 的 `setup_logging(settings)` SHALL 使用 `settings.log_format` 创建 `Formatter`，不再在代码中硬编码格式字符串。其余行为（目录创建、FileHandler/AsyncFileHandler 创建、根 logger 注册、handler 去重）保持不变。

#### Scenario: 格式来自 settings
- **WHEN** `setup_logging(settings)` 被调用
- **THEN** `Formatter` 使用 `settings.log_format` 的值，而非硬编码字符串

### Requirement: scripts/start.sh master 日志路径一致性
`scripts/start.sh` 中 master 服务的 stdout/stderr 重定向目标 SHALL 与 `master/core/settings.py` 中 `settings.log_dir` 指向的路径一致。脚本不再为 master 单独定义 `$PROJECT_ROOT/logs/master.log`。

#### Scenario: 脚本启动与直接启动日志路径一致
- **WHEN** 通过 `scripts/start.sh master` 启动 master
- **THEN** stdout/stderr 重定向到的文件路径等于 `settings.log_dir` 的值

#### Scenario: 状态展示日志路径
- **WHEN** 执行 `scripts/start.sh status` 或 `scripts/stop.sh status`
- **THEN** 显示的 master 日志路径来自 `settings.log_dir`，而非硬编码的 `$PROJECT_ROOT/logs/master.log`

## REMOVED Requirements
无。
