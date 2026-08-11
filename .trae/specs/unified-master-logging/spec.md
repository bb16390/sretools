# Master 服务统一日志与启动管理 - Product Requirement Document

## Overview
- **Summary**: 统一 Master 服务在两种启动方式下（直接运行 `master/main.py` 与通过 `scripts/start.sh` 脚本启动）的 uvicorn 配置、日志格式、日志路径，所有配置项统一集中在 `master/core/settings.py` 中定义，确保行为一致性。
- **Purpose**: 解决当前两套启动机制产生的日志路径分裂、日志格式不统一、uvicorn 参数（host/port/access_log/reload 等）来源不一致的问题，便于运维排查、日志收集与行为预测。
- **Target Users**: 项目开发者、运维人员、使用脚本或直接启动 master 的使用者。

## Goals
- 在 `master/core/settings.py` 中集中定义所有 uvicorn 与日志相关配置。
- 两种启动方式（直接运行 main.py / scripts 脚本）使用完全一致的日志格式、日志文件路径、日志级别。
- 两种启动方式下 uvicorn 的 host、port、access_log、reload、workers 等参数均来自 settings.py，保持一致。
- uvicorn 内部日志（uvicorn.error、uvicorn.access 等 logger）也复用统一的日志格式与输出路径。
- 脚本启停不再额外将 stdout/stderr 重定向至与 settings 冲突的文件；如有 shell 层输出也应对齐 settings 路径。

## Non-Goals (Out of Scope)
- 不改造 Worker 服务的日志与启动流程（本次仅针对 Master）。
- 不更换日志框架（仍使用标准 logging + 现有 AsyncFileHandler）。
- 不引入新的第三方日志库（如 structlog、loguru）。
- 不改变现有业务代码的 logger 调用方式。
- 不负责日志轮转、切割等高级策略（仅保证路径与格式统一）。

## Background & Context
- 当前 Master 有两条启动路径：
  1. **直接启动**：`python master/main.py` 或 `python -m master.main`，在 `__main__` 块内实例化 `uvicorn.Config` 并运行，host/port 取自 settings.py，但未向 uvicorn 传入自定义 `log_config`。
  2. **脚本启动**：`scripts/start.sh` 中 `cd $MASTER_DIR && uv run python -m uvicorn main:app ...`，host/port 来自 shell 环境变量 `$HOST/$PORT`（默认 0.0.0.0:5500），并通过 `nohup ... > $PROJECT_ROOT/logs/master.log 2>&1` 重定向 stdout/stderr。
- 现有 `settings.py` 已定义 `log_level`、`log_dir`（`master/log/uvicorn.log`）、`error_log_dir`（`master/log/uvicorn-error.log`），但脚本实际写入 `PROJECT_ROOT/logs/master.log`，造成两套日志文件并存，运维定位困难。
- `master/core/logging.py` 中 `setup_logging(settings)` 会向根 logger 挂载 `AsyncFileHandler`，格式为 `%(asctime)s - %(name)s - %(levelname)s - %(message)s`，但 uvicorn 内置 logger（access/error）默认使用 uvicorn 自带 LOG_CONFIG，格式与输出目标不一致。

## Functional Requirements
- **FR-1**: `master/core/settings.py` 新增或完善以下配置项（缺失则补齐），且所有项均提供合理默认值：
  - uvicorn 运行参数：`host`、`port`、`reload`、`access_log`（布尔）、`workers`、`log_level`（字符串，与 uvicorn LOGGING_CONFIG 级别兼容）。
  - 日志输出路径：`log_dir`（主日志文件绝对路径）、`uvicorn_access_log`（access 日志路径）、`uvicorn_error_log`（uvicorn 错误日志路径，可与主日志合流或独立）。
  - 日志格式：`log_format`（字符串模板，用于业务与 uvicorn 共用）、`access_log_format`（字符串，用于 uvicorn access）、`log_datefmt`（时间格式）。
- **FR-2**: `master/core/logging.py` 提供 `build_uvicorn_log_config(settings) -> dict` 函数，生成与 uvicorn `LOGGING_CONFIG` schema 兼容的字典，并确保：
  - handlers 使用与 `setup_logging` 一致的 formatter 与 settings 中的文件路径（可复用 `AsyncFileHandler` 或普通 `FileHandler`，需注明选型）。
  - `uvicorn`、`uvicorn.error`、`uvicorn.access` 三个 logger 均指向统一配置。
  - 日志级别取自 `settings.log_level`。
- **FR-3**: `master/main.py`：
  - `__main__` 分支中使用 FR-2 的 `build_uvicorn_log_config(settings)` 结果作为 `uvicorn.Config(log_config=...)` 参数。
  - uvicorn `host`/`port`/`reload`/`access_log` 等参数全部从 settings 取值，不再硬编码。
  - 保持现有 `setup_logging(settings)` 调用（作用于业务 logger），但要避免与 uvicorn log_config 重复挂载 handler 导致日志双倍写出。
- **FR-4**: `scripts/start.sh` 的 `start_master` 函数：
  - **不再** 通过 shell 重定向 `> $MASTER_LOG 2>&1` 将 uvicorn stdout/stderr 指向独立日志文件（或仅保留必要的 crash stdout 输出到 settings 指定路径，禁止写入与 settings 不同的日志文件）。
  - 启动命令使用 `uvicorn` 的 `--log-config`/`--log-level`/`--access-log`/`--no-access-log` 参数；或等价地：用 `python -c` 入口调用与 `main.py` 中相同的代码路径（即复用 FR-3 的配置生成逻辑）。
  - `host`/`port` 不再从 shell `$HOST/$PORT` 取值，改为以 settings.py 为准；若要支持覆盖需通过 settings 本身可识别的环境变量（例如 pydantic-settings 自动注入的同名 env）。
- **FR-5**: 启动脚本的日志提示信息（“日志文件: xxx”）需打印 settings 中实际使用的日志路径，而非旧的 `$PROJECT_ROOT/logs/master.log`。
- **FR-6**: `setup_logging` 与 `build_uvicorn_log_config` 共享 formatter 字符串、日期格式与日志级别，确保业务日志行与 uvicorn 日志行在同一文件/同一体系下可读、可 grep。

## Non-Functional Requirements
- **NFR-1**: 兼容性：改造后现有业务 logger 调用（`logger.info/error` 等）输出内容不变，仅格式与落点统一；不得引入运行时异常。
- **NFR-2**: 幂等性：多次调用 `setup_logging` / 多次初始化 uvicorn（例如 reload 场景）不得导致 handler 重复叠加或日志重复写入。
- **NFR-3**: 可观测性：两种启动方式写入的日志文件路径对用户可发现（settings 中有清晰字段、启动时脚本打印、logger 启动时可打印一行"Logging to: <path>"）。
- **NFR-4**: 性能：复用现有 AsyncFileHandler 的前提下，uvicorn 高并发 access 日志不得引入明显阻塞；若选型为普通 FileHandler，文档需说明原因并给出后续优化建议。
- **NFR-5**: 代码可读性：settings 字段命名清晰、注释齐全；logging 工具函数提供 docstring，说明输入/输出 schema。

## Constraints
- **Technical**: 必须使用 Python 标准库 `logging` + uvicorn 自带 `LOGGING_CONFIG` schema；不得引入新的第三方日志依赖。Python 版本 >= 3.12，uvicorn 由项目依赖安装（fastapi 0.111.0 对应可用版本）。
- **Business**: 不得破坏现有 `scripts/stop.sh`、`scripts/deploy.sh`、`scripts/upgrade.sh` 的进程管理逻辑（PID 文件、健康检查、进程组清理保持不变）。
- **Dependencies**: 仅依赖现有 `master/core/settings.py` 的 Settings 类与 `master/core/logging.py` 的 `AsyncFileHandler`/`setup_logging`，不得改动 worker 模块。

## Assumptions
- 假设 settings.py 可继续通过 `fastapi_amis_admin.admin.Settings` 继承（pydantic v1/v2 行为需确认，但本改造默认字段取值即可）。
- 假设 uvicorn 接受 `log_config=dict` 参数，且 `disable_existing_loggers=False` 不会与 `setup_logging` 预挂载的 handler 冲突（若冲突则采用其中一方负责挂载，另一方做幂等去重）。
- 假设 CI 或部署环境中允许 master 进程写入 `master/log/` 目录；若将来要迁到 `logs/`，仅改 settings 默认值即可。
- 假设 `scripts/start.sh` 的 `$MASTER_LOG` shell 变量可移除或仅指向 settings 同一路径，不被外部其他系统依赖。

## Acceptance Criteria

### AC-1: Settings 集中配置
- **Given**: 代码完成改造
- **When**: 开发者阅读 `master/core/settings.py`
- **Then**: 可以在该文件内找到以下字段且有默认值：`host`、`port`、`reload`、`access_log`、`workers`、`log_level`、`log_dir`（主日志）、`uvicorn_access_log`、`uvicorn_error_log`、`log_format`、`access_log_format`、`log_datefmt`
- **Verification**: `human-judgment`
- **Notes**: 字段名可在实现阶段微调，但须全部集中存在于 settings.py 且彼此无冲突。

### AC-2: 直接启动日志路径正确
- **Given**: 项目依赖已安装、master 目录可写
- **When**: 执行 `cd /workspace && python -m master.main`（或等价直接启动方式），产生至少一条 INFO 级业务日志与一次 HTTP 请求
- **Then**: 业务日志与 uvicorn access/error 日志均写入 `settings.log_dir` / `settings.uvicorn_access_log` 指定的路径，不写入除此之外的其他日志文件
- **Verification**: `programmatic`

### AC-3: 脚本启动与直接启动路径完全一致
- **Given**: 通过 `scripts/start.sh start master` 启动成功
- **When**: 触发相同业务日志与 HTTP 请求
- **Then**: 写入的日志文件路径（绝对路径）与 AC-2 直接启动时完全一致；`logs/master.log` 这类与 settings 不同名的文件不再被创建（或为空/未使用）
- **Verification**: `programmatic`
- **Notes**: 须在干净环境（先删除历史日志）下验证。

### AC-4: 日志格式一致
- **Given**: 两种启动方式分别产生的日志行样本
- **When**: 对比日志行格式（非时间值本身）
- **Then**: 业务日志行均匹配 `settings.log_format` 模板；uvicorn access 日志行匹配 `settings.access_log_format`；时间格式遵循 `settings.log_datefmt`
- **Verification**: `programmatic`

### AC-5: uvicorn 参数来源统一
- **Given**: 未设置 `HOST`/`PORT` 等 shell 环境变量（或设置与 settings 默认不同）
- **When**: 分别用直接启动与脚本启动 Master
- **Then**: 监听的 host/port 均等于 settings 中的默认值（或 settings 自身支持的 env 覆盖），不等于 start.sh 脚本内部的 `0.0.0.0/5500` 硬编码回退
- **Verification**: `programmatic`

### AC-6: 无重复日志写入
- **Given**: 通过任一方式启动，向根 logger 或应用 logger 写入一条 INFO
- **When**: 检查目标日志文件
- **Then**: 该条日志仅出现一次；uvicorn access 日志每行也仅出现一次
- **Verification**: `programmatic`

### AC-7: 脚本停止逻辑未受影响
- **Given**: Master 通过脚本启动并记录 PID
- **When**: 执行 `scripts/stop.sh stop master` 或 `scripts/start.sh stop master`
- **Then**: 进程正常退出，PID 文件被清理，端口释放；日志文件中可见“优雅停机”类结束日志
- **Verification**: `programmatic`

### AC-8: 启动日志路径提示准确
- **Given**: 使用脚本启动 master
- **When**: 查看脚本 stdout
- **Then**: “日志文件: <path>” 行显示的路径等于 settings 中主日志路径（`settings.log_dir`）
- **Verification**: `programmatic`

## Open Questions
- [ ] `log_dir`、`uvicorn_access_log`、`uvicorn_error_log` 是否要全部独立文件，还是 access 与 error 都合流到主日志 `log_dir`？（影响 formatter filter 与 handler 复用方式）
- [ ] 脚本层是否需要保留一份最小的 stdout/stderr（例如写到与 settings 同目录的 `.out` 文件）用于排查进程刚启动就崩溃、Python 解释器级别错误？
- [ ] `reload` 默认值应该保持开发友好（True）还是生产默认关闭（False）？需明确用途与推荐部署方式。
- [ ] 当前 `AsyncFileHandler` 基于 `QueueHandler` 做异步写，是否要同时用于 uvicorn access/error logger（高吞吐场景），还是 uvicorn 先使用同步 FileHandler 即可？
