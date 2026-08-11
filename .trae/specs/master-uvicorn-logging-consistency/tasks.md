# Master Uvicorn 日志配置一致性 - 实施计划

## [x] Task 1: 完善 settings.py 中的 uvicorn 与日志配置字段（含轮转参数）
- **Priority**: high
- **Depends On**: None
- **Description**:
  - 在 `master/core/settings.py` 的 `Settings` 类中新增 uvicorn 运行参数：`uvicorn_reload: bool`、`uvicorn_workers: int`、`uvicorn_access_log: bool`，并提供合理默认值
  - 新增日志格式字段：`log_format: str`（应用日志格式）、`access_log_format: str`（uvicorn access log 格式），提供默认值
  - 梳理并统一日志文件路径字段：将命名误导的 `log_dir` 语义明确化（如保留名但加注释，或重命名为 `log_file`），并新增/调整相关字段，使日志目录统一指向 `$PROJECT_ROOT/logs/`（与 scripts 一致）；错误日志与 access log 文件路径也一并配置化
  - **新增轮转参数字段**：`log_rotation_when: str`（默认 `"midnight"`，每日零点轮转）、`log_rotation_interval: int`（默认 `1`，每 1 个 when 单位轮转一次）、`log_backup_count: int`（默认 `30`，保留 30 份）、`log_rotation_encoding: str`（默认 `"utf-8"`）
  - 保持 MASTER_DIR / PROJECT_ROOT 路径推导正确，同时引用 settings 的其他代码不受破坏（如 setup_logging 现有调用）
  - 新增字段以项目根目录推导 `PROJECT_ROOT`（MASTER_DIR 的父目录）
- **Acceptance Criteria Addressed**: AC-1, AC-8, AC-9
- **Test Requirements**:
  - `programmatic` TR-1.1: 在 Python 中导入 `master.core.settings.settings`，属性 `uvicorn_reload`、`uvicorn_workers`、`uvicorn_access_log`、`log_format`、`access_log_format` 均存在且类型正确
  - `programmatic` TR-1.2: `settings.log_file`（或对应字段）解析后的绝对路径位于 `$PROJECT_ROOT/logs/` 下，父目录位于项目根
  - `programmatic` TR-1.3: `settings` 能通过 pydantic 校验（无类型错误，默认值完整），轮转参数 `log_rotation_when`/`log_rotation_interval`/`log_backup_count`/`log_rotation_encoding` 全部可读且默认值合理
- **Notes**: 重命名字段时需搜索所有引用处一并调整；PROJECT_ROOT 可基于现有 MASTER_DIR 推导 `os.path.dirname(MASTER_DIR)`

## [x] Task 2: 增强 setup_logging()，统一配置应用与 uvicorn 日志（含按日轮转）
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - 修改 `master/core/logging.py`：
    1. **引入 `logging.handlers.TimedRotatingFileHandler`**，`AsyncFileHandler` 内部包装的底层 handler 类型由 `FileHandler` 改为 `TimedRotatingFileHandler`，但签名仍保持"接收一个底层 handler 实例并包装"（保持通用），`setup_logging` 中创建并传入 `TimedRotatingFileHandler(when=settings.log_rotation_when, interval=settings.log_rotation_interval, backupCount=settings.log_backup_count, encoding=settings.log_rotation_encoding, ...)`
    2. `setup_logging(settings)` 中使用 settings 的 `log_format`/`access_log_format` 创建 formatter，不再硬编码格式字符串
    3. 创建三类 logger：根 logger `""`、uvicorn 基础 logger `"uvicorn"`、uvicorn error logger `"uvicorn.error"`、uvicorn access logger `"uvicorn.access"`
    4. 为它们分别（或统一）添加 `AsyncFileHandler` 包装的 `TimedRotatingFileHandler`，文件路径、级别均来自 settings；主日志/access log/error log 各自使用独立的 TimedRotatingFileHandler 实例（即独立轮转周期与备份计数）
    5. access log 可选择独立文件（使用 `access_log_format`），与应用日志分开或合并按 settings 配置决定
    6. 对每类 logger 都执行去重逻辑：添加 handler 前若已存在同类 AsyncFileHandler，则先移除避免重复
  - 新增工具函数 `get_uvicorn_log_config(settings) -> dict`，返回符合 uvicorn `log_config` 参数格式的 dictConfig（version:1, formatters, handlers, loggers），其核心目标是 `disable_existing_loggers=False` 并且不添加任何 handler，以避免覆盖 setup_logging 已经注册的 AsyncFileHandler+TimedRotatingFileHandler 组合
- **Acceptance Criteria Addressed**: AC-2, AC-6, AC-9, AC-10
- **Test Requirements**:
  - `programmatic` TR-2.1: 调用 `setup_logging(settings)` 后，`logging.getLogger("uvicorn.access")` 的 handlers 列表包含至少一个 AsyncFileHandler 包装的 handler，其底层 `_file_handler` 类型为 `TimedRotatingFileHandler`，级别等于 settings.log_level
  - `programmatic` TR-2.2: access logger 使用的 formatter 格式字符串等于 settings.access_log_format
  - `programmatic` TR-2.3: 连续调用两次 `setup_logging(settings)`，根 logger 的 handlers 数量不增加，输出日志不重复
  - `programmatic` TR-2.4: 向 `uvicorn.access` logger 输出日志后，对应的 access log 文件存在并包含日志内容
  - `programmatic` TR-2.5: 取根 logger 对应的底层 TimedRotatingFileHandler，调用其 `doRollover()` 后，原日志文件被归档为带日期后缀的文件，新的主日志文件继续接收后续写入；归档文件编码使用 utf-8 且内容正确
  - `programmatic` TR-2.6: 在异步写入期间（队列中仍有日志时）调用轮转，日志不丢失，归档与新文件内容之和等于写入总条数
- **Notes**: 可参考现有 tests/dashboard/core/test_logging.py 中的测试模式；如果 access log 选择独立文件，记得在 setup_logging 中为其单独创建目录；轮转测试使用临时目录，测试完成后清理

## [x] Task 3: 统一 master/main.py 的 uvicorn 启动配置（含 __main__ 分支）
- **Priority**: high
- **Depends On**: Task 1, Task 2
- **Description**:
  - 在 `master/main.py` 中新增函数 `build_uvicorn_kwargs(settings) -> dict`：返回传递给 `uvicorn.Config` 或 `uvicorn.run` 的完整关键字参数字典，包含 host、port、reload、workers、access_log（注意 uvicorn 自身的 access_log 参数只是布尔开关，而 handler 已由 setup_logging 注册）、log_config 等，值全部来自 settings
  - 修改 `if __name__ == "__main__":` 分支：不再硬编码 `access_log=True, reload=True`，改为使用 `build_uvicorn_kwargs(settings)` 的返回构造 uvicorn.Config
  - 保证 `setup_logging(settings)` 在 app 创建前、uvicorn 启动前被调用（目前位置正确但需要确认 uvicorn log_config 不会覆盖 setup_logging 的效果）
  - 注意：`uvicorn.run` 的 `log_config` 参数如果传入 `None` 会使用 uvicorn 默认 dictConfig 并覆盖已有 handler；需明确传入禁用默认配置的方式（例如自定义的 log_config dict 不添加任何 handler，或使用 `--log-config` 指向自定义，但更稳妥的方式是让 setup_logging 完成后，传给 uvicorn 的 log_config 为一个不包含任何 handler 的最小化 dict，只设置 disable_existing_loggers=False）
- **Acceptance Criteria Addressed**: AC-3, AC-5, AC-8
- **Test Requirements**:
  - `programmatic` TR-3.1: 调用 `build_uvicorn_kwargs(settings)` 返回的 dict 中包含 `host`、`port`、`reload`、`workers`、`access_log` 等键，值与 settings 对应字段完全一致
  - `programmatic` TR-3.2: 以非阻塞方式启动 `uv run python -m master.main` 后（短时间），进程未立即崩溃，监听端口与 settings.port 一致（通过健康检查或 netstat）
  - `programmatic` TR-3.3: 访问一次 `/` 后，settings 指定的 master.log 文件中包含 access log 行和应用 `应用启动完成` 行
- **Notes**: 由于 uvicorn log_config 默认会 `disable_existing_loggers=True`，务必传入的 dictConfig 中明确 `disable_existing_loggers=False` 且避免重复添加 handler

## [x] Task 4: 改造 scripts/start.sh 中 start_master 日志重定向与启动方式
- **Priority**: high
- **Depends On**: Task 3
- **Description**:
  - 确认并统一启动入口：推荐使用从 `PROJECT_ROOT` 执行 `uv run python -m master.main`（走 `__main__` 分支，自然复用 Task 3 中 build_uvicorn_kwargs 逻辑），而不是 `python -m uvicorn main:app`，避免两套启动参数分叉
  - 移除或改造 `nohup ... > "$MASTER_LOG" 2>&1` 中的重定向：由于 Python 内部已按 settings 统一写文件，shell 层面的 stdout/stderr 只需保留少量启动信息（可指向 `/dev/null` 或另一个 `stdout.log`，但不再宣称是"主日志"）
  - 脚本中 `MASTER_LOG="$LOG_DIR/master.log"` 的路径定义：改为从 settings 读取或保证与 settings 中 `log_file` 计算结果完全一致（默认 `$PROJECT_ROOT/logs/master.log`）；scripts 的 `log_info` 提示"日志文件: xxx"应指向 settings 中的主日志文件路径
  - host/port 读取：脚本中的 `HOST`/`PORT` 环境变量仍可保留作为可选覆盖，但默认情况下不再硬编码 `0.0.0.0:5500` 的值，而是以 settings 为准（若需要在脚本层面知晓端口，可通过 `python -c "from master.core.settings import settings; print(settings.port)"` 取得）
  - `access_log=False`/`True` 参数也不再在 shell 命令行硬编码，统一由 settings 生效
- **Acceptance Criteria Addressed**: AC-4, AC-5, AC-7
- **Test Requirements**:
  - `programmatic` TR-4.1: 运行 `./scripts/start.sh start master --skip-deps --no-wait` 后，检查 `$PROJECT_ROOT/logs/master.log` 文件存在且包含 uvicorn 启动 banner（如 "Uvicorn running on http://..." 或由 setup_logging 记录的启动日志）
  - `programmatic` TR-4.2: 启动后检查 `$PROJECT_ROOT/logs/master.log` 中的第一行格式符合 settings.log_format（存在 asctime/name/levelname 字段）
  - `programmatic` TR-4.3: 对比 Task 3 直接启动与脚本启动产生的日志文件，两者格式字符串一致、路径一致、包含相同关键字段（access log 行也存在）
  - `programmatic` TR-4.4: `./scripts/stop.sh stop master` 能优雅停止由 start.sh 启动的进程，PID 文件清理干净
- **Notes**: shell 中从 settings 读取端口等信息时，注意 `uv run` 环境的一致性；若暂时不方便解析，可先保证默认值 5500 与 settings 对齐并加 TODO 注释

## [x] Task 5: 清理遗留引用与文档同步（停止脚本兼容 + settings 字段重命名影响）
- **Priority**: medium
- **Depends On**: Task 1, Task 2, Task 3, Task 4
- **Description**:
  - 搜索 `error_log_dir`、`log_dir` 等旧字段名在项目中的所有引用（含 tests、worker、master 其他模块），确保已同步更新为新字段名或保留兼容别名
  - 检查 `scripts/stop.sh` 与 `scripts/upgrade.sh` / `deploy.sh` 中是否有引用 master 日志路径或启动参数，如有则同步对齐
  - 若 `scripts/start.sh` 中的 `MASTER_LOG` 变量现在只用于提示，确认不再依赖该变量做其他处理
  - 清理 `master/core/logging.py` 中因字段重命名不再需要的 `os.path.dirname(settings.log_dir)` 写法（如果 log_file 已是完整文件路径）
- **Acceptance Criteria Addressed**: AC-7, AC-8
- **Test Requirements**:
  - `programmatic` TR-5.1: 全项目搜索 `log_dir` 非注释引用不再指向 settings 中旧字段（或全部已兼容处理）
  - `programmatic` TR-5.2: 运行现有日志相关测试 `pytest tests/dashboard/core/test_logging.py tests/dashboard/core/test_logging_performance.py` 全部通过
  - `human-judgement` TR-5.3: stop.sh / start.sh 中 status 命令展示的日志目录与实际一致
- **Notes**: 若发现 tests 对旧字段有依赖，同步更新；worker/core/settings.py 中的同名字段如有，不要改动，仅改 master

## [/] Task 6: 集成回归测试与最终人工核对
- **Priority**: high
- **Depends On**: Task 5
- **Description**:
  - 编写端到端验证：以两种启动方式分别启动 master，验证监听端口、日志路径、access log 写入、停止行为一致
  - 对两种方式启动后的 master 分别发起 HTTP 请求，对比日志中 access log 的格式与位置
  - 人工确认：不再有 `master/log/uvicorn.log` 与 `logs/master.log` 双写分裂
- **Acceptance Criteria Addressed**: AC-3, AC-4, AC-5, AC-8
- **Test Requirements**:
  - `programmatic` TR-6.1: 直接启动方式下，`logs/master.log` 包含启动日志 + access log，且 `master/log/uvicorn.log` 不再被创建
  - `programmatic` TR-6.2: 脚本启动方式下，`logs/master.log` 同 TR-6.1 内容；同时 `nohup.out`（如有）不再承载主日志
  - `human-judgement` TR-6.3: 审阅 start.sh 与 main.py 中所有日志/uvicorn 配置，确认不再有硬编码路径或格式字符串散落在 settings 之外
- **Notes**: 测试完成后清理创建的日志文件和 .pids，避免污染工作区
