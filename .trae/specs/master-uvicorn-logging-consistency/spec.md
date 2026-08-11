# Master Uvicorn 日志配置一致性 - 产品需求文档

## Overview
- **Summary**: 统一 master 服务的启动方式，确保通过 `scripts/start.sh` 启停脚本与直接运行 `master/main.py` 两种方式启动时，uvicorn 的配置（host、port、reload 等）及日志系统的格式、路径、级别等完全一致，所有配置均收敛于 `master/core/settings.py` 中。
- **Purpose**: 解决当前不同启动方式下日志路径分离（脚本输出到 `logs/master.log`，Python 内部写入 `master/log/uvicorn.log`）、uvicorn access log 格式不一致、配置分散（部分在 main.py、部分在 shell 脚本硬编码）等问题，提升运维可观测性和配置一致性。
- **Target Users**: 开发人员、运维人员，需要启停 master 服务并查看日志的用户。

## Goals
- **G-1**: 将 uvicorn 相关运行参数（host、port、reload、workers 等）全部配置化到 `master/core/settings.py`
- **G-2**: 将日志路径、日志格式、日志级别等全部配置化到 `master/core/settings.py`
- **G-3**: 统一两种启动方式（`python master/main.py` 与 `scripts/start.sh`）的日志输出路径和格式
- **G-4**: uvicorn 自身的 access log、error log 也纳入统一的日志配置体系
- **G-5**: `setup_logging()` 能同时配置应用日志与 uvicorn 日志，保证两者格式、路径、级别一致

## Non-Goals (Out of Scope)
- 不修改 worker 模块的日志/启动方式（仅聚焦 master）
- 不引入新的日志框架（仍使用标准库 logging + uvicorn 默认 log_config 机制）
- 不修改日志异步写入机制（保留现有 `AsyncFileHandler`）
- 不做日志轮转（rotate）策略的变更，仅保证路径格式一致
- 不重构 scripts 中的整体架构（仅修改 master 启停相关部分）

## Background & Context
- 当前项目 master 入口为 `master/main.py`，内部使用 FastAPI + uvicorn 运行
- 当前存在两种启动方式：
  1. **直接启动**：`cd master && python main.py`，走 `if __name__ == "__main__"` 分支，`uvicorn.run(app, host=settings.host, port=settings.port, access_log=True, reload=True)`，应用日志写入 `master/log/uvicorn.log`
  2. **脚本启动**：`scripts/start.sh start master`，走 `cd $MASTER_DIR && uv run python -m uvicorn main:app --host --port`，stdout/stderr 通过 `nohup` 重定向到 `$PROJECT_ROOT/logs/master.log`
- 两种方式的核心差异：
  - **日志路径冲突**：应用内部 handler 写 `master/log/uvicorn.log`，脚本 shell 重定向写 `logs/master.log`，日志分裂在两处
  - **uvicorn access log 缺失统一 handler**：`main.py` 中 `access_log=True` 但 uvicorn 默认走其内部 log_config，没有被 `setup_logging()` 覆盖
  - **配置散落**：reload 只在直接启动时开启、host/port 脚本用环境变量覆盖而非 settings
- `master/core/settings.py` 已存在 `log_dir`（命名误导，实为文件路径）、`error_log_dir`、`log_level` 字段，但缺少格式字符串、uvicorn 参数等配置
- `master/core/logging.py` 中已有 `setup_logging(settings)` 和 `AsyncFileHandler`，但仅配置根 logger，未配置 uvicorn 专属 logger（`uvicorn`、`uvicorn.access`、`uvicorn.error`）

## Functional Requirements
- **FR-1**: `master/core/settings.py` 中新增/完善 uvicorn 运行参数配置字段：
  - `uvicorn_reload: bool`（是否开启 reload，默认开发环境 True）
  - `uvicorn_workers: int`（worker 数，默认 1）
  - `uvicorn_access_log: bool`（是否开启 access log，默认 True）
- **FR-2**: `master/core/settings.py` 中新增/完善日志配置字段：
  - `log_format: str`（日志格式字符串，提供默认值）
  - `access_log_format: str`（uvicorn access log 格式字符串，提供默认值）
  - 将命名误导的 `log_dir` 调整为语义清晰的字段（如 `log_file`、`access_log_file`、`error_log_file`），或保留字段名但确保注释清晰，并统一日志目录为 `$PROJECT_ROOT/logs/`（与 scripts 的 `LOG_DIR` 一致）
- **FR-3**: `master/core/logging.py` 中 `setup_logging(settings)` 增强：
  - 同时配置根 logger 与 uvicorn 相关 logger（`uvicorn`、`uvicorn.access`、`uvicorn.error`）
  - 所有 logger 使用 settings 中的级别、格式
  - access log 与 error log 可分别写入 settings 指定文件（或统一文件，由 settings 决定）
  - 保持 `AsyncFileHandler` 异步写入能力
  - 去重逻辑：避免多次调用时 handler 堆叠
- **FR-4**: 提供统一的 uvicorn 配置入口：
  - 在 `master/core/settings.py` 或 `master/core/logging.py` 中提供 `get_uvicorn_log_config(settings)` 函数，返回 uvicorn 接受的 `log_config` dict，其路径/格式/级别均来自 settings
  - 在 `master/main.py` 中提供 `get_uvicorn_config(settings)` 函数，构造完整的 `uvicorn.Config` 所需参数（host/port/reload/workers/log_config 等），供 `__main__` 分支和外部调用者使用
- **FR-5**: `master/main.py` 的 `__main__` 分支改造：
  - 不再硬编码 `access_log=True`、`reload=True`
  - 使用 FR-4 中的统一配置函数构造 uvicorn 启动参数
  - 确保 `setup_logging(settings)` 在 uvicorn 启动前正确调用
- **FR-6**: `scripts/start.sh` 的 `start_master()` 改造：
  - 不再依赖环境变量硬编码 host/port（或仅作为 settings 的可选覆盖）
  - 不再通过 shell `nohup > file` 重定向 stdout/stderr 作为主日志（因为 Python 内部已统一写文件）
  - 使用 uv run 方式从项目根目录启动，调用统一入口（推荐：`uv run python -m master.main` 走 `__main__`，或 `uvicorn master.main:app --log-config <...>` 但需要确保 FR-3/FR-4 生效）
  - 脚本层面仅保留启动/停止进程管理、健康检查、PID 管理等功能，不再负责日志输出路径
  - 脚本中提示的"日志文件路径"应与 settings 中配置一致

## Non-Functional Requirements
- **NFR-1**: 向后兼容：现有 settings 的行为应尽量平滑过渡，字段重命名应提供兼容别名或同步更新所有引用处
- **NFR-2**: 两种启动方式产生的日志内容、格式、路径字节级一致（除了启动时间等差异）
- **NFR-3**: 性能：`AsyncFileHandler` 批处理机制保持，不因引入多个 logger 而退化
- **NFR-4**: 可观测性：启动完成后，uvicorn access log（如 `127.0.0.1:xxx - "GET / HTTP/1.1" 200`）与应用内部 `logger.info()` 出现在同一日志文件（或按 settings 分离但路径明确），格式统一带时间戳/logger 名/级别
- **NFR-5**: 启停脚本 `start.sh` / `stop.sh` 在改造后，`status`、`restart`、`--force` 等其他功能保持不变

## Constraints
- **Technical**:
  - 语言/框架：Python 3.12+，uvicorn，标准库 logging
  - 不新增第三方日志库（不使用 loguru 等）
  - 必须保留 `AsyncFileHandler`（已有异步写入逻辑）
- **Business**:
  - 不能破坏现有 worker 的启停逻辑（仅改 master）
  - 应保证在使用 `uv sync` 环境下正常工作
- **Dependencies**:
  - 现有 `fastapi==0.111.0`、`uvicorn`（通过 fastapi 依赖引入）
  - `master/core/settings.py` 继承自 `fastapi_amis_admin.admin.Settings`（pydantic-settings）

## Assumptions
- **A-1**: 用户期望日志统一输出到 `$PROJECT_ROOT/logs/` 目录下（与当前 scripts 中 `LOG_DIR=$PROJECT_ROOT/logs` 一致），而非 `master/log/` 子目录
- **A-2**: `uvicorn_reload` 在生产/脚本启动场景下默认应为 False，开发直接启动时为 True（或统一由 settings 控制，脚本不再强制差异化）
- **A-3**: `scripts/stop.sh` 独立存在且与 `start.sh` 功能重叠，本次改造聚焦 start.sh 的 master 部分；stop.sh 保持不变但应验证兼容性
- **A-4**: uvicorn access log 建议写入独立文件（如 `master-access.log`）或与应用日志合并，具体由 settings 默认值决定，但需统一

## Acceptance Criteria

### AC-1: settings 配置完备性
- **Given**: 用户打开 `master/core/settings.py`
- **When**: 检查 Settings 类字段
- **Then**: 存在 uvicorn 运行参数字段（reload、workers、access_log 开关）以及日志字段（格式字符串、文件路径），且字段名语义清晰、注释完整
- **Verification**: `programmatic`
- **Notes**: 可以通过导入 Settings 实例检查属性存在性

### AC-2: setup_logging 同时配置 uvicorn logger
- **Given**: `setup_logging(settings)` 已调用
- **When**: 检查 logging.getLogger("uvicorn")、logging.getLogger("uvicorn.access")、logging.getLogger("uvicorn.error")
- **Then**: 这些 logger 已添加 handler，级别与 settings.log_level 一致，formatter 使用 settings.log_format（access logger 可使用 access_log_format）
- **Verification**: `programmatic`

### AC-3: 直接启动 master/main.py 日志正确输出
- **Given**: settings 中 log_file 指向 `$PROJECT_ROOT/logs/master.log`
- **When**: 在项目根目录执行 `uv run python -m master.main` 启动服务，访问一次 `/`，然后停止
- **Then**:
  1. `$PROJECT_ROOT/logs/master.log` 存在
  2. 文件中包含应用启动日志（`应用启动完成` 等）
  3. 文件中包含 uvicorn access log（GET / 200）
  4. 每行日志格式统一为 settings.log_format（含 asctime/name/levelname/message）
- **Verification**: `programmatic`

### AC-4: scripts/start.sh 启动日志与直接启动一致
- **Given**: settings 配置与 AC-3 相同
- **When**: 执行 `./scripts/start.sh start master` 启动服务，访问一次 `/`，然后 `./scripts/stop.sh stop master` 停止
- **Then**:
  1. 日志文件路径与 AC-3 完全相同（`logs/master.log`），不再额外输出到 shell 重定向文件
  2. 日志内容、格式与直接启动的日志字节级一致（除 PID、时间戳等差异）
  3. `start.sh` 提示的"日志文件"路径与 settings 实际路径一致
- **Verification**: `programmatic`

### AC-5: 两种启动方式 uvicorn 运行参数一致
- **Given**: settings 中 uvicorn_reload=False, uvicorn_workers=1, host/port 为默认值
- **When**: 分别用两种方式启动 master，观察 uvicorn 启动日志和监听端口
- **Then**:
  1. 两种方式监听 host/port 均来自 settings（如 0.0.0.0:5500）
  2. reload 行为一致（不因 shell 脚本/直接启动而不同）
  3. access log 行为一致（同开同关）
- **Verification**: `programmatic`

### AC-6: setup_logging 可重复调用幂等
- **Given**: 已调用过一次 `setup_logging(settings)`
- **When**: 再次调用 `setup_logging(settings)` 并输出一条日志
- **Then**: 根 logger 与 uvicorn logger 的 handler 数量不变，日志不会重复输出
- **Verification**: `programmatic`

### AC-7: 停止脚本兼容
- **Given**: 通过 `start.sh start master` 启动了 master 并写入 PID 文件
- **When**: 执行 `./scripts/stop.sh stop master`
- **Then**: 进程被优雅停止，PID 文件清理，无残留进程
- **Verification**: `programmatic`

### AC-8: 配置集中性审计
- **Given**: 改造完成后的代码库
- **When**: 全文搜索 host/port/log path/log format 等关键字在 master 相关代码中的出现位置
- **Then**: 除 `master/core/settings.py` 定义处和读取处外，无硬编码的日志路径、格式或 uvicorn 运行参数；scripts 中仅保留读取/展示逻辑，不硬编码值
- **Verification**: `human-judgment`

## Open Questions
- [ ] 日志最终输出路径：确认统一到 `$PROJECT_ROOT/logs/master.log`（与脚本现有 LOG_DIR 一致）是否符合预期？还是保留 `master/log/` 并修改 scripts？
- [ ] access log 是否需要独立文件（如 `logs/master-access.log`）？还是与应用日志合并写入同一文件？
- [ ] 字段重命名：`settings.log_dir` 实际上是文件路径，是否需要重命名为 `log_file` 并同步修改所有引用？
