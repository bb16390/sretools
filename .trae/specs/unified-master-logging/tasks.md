# Master 服务统一日志与启动管理 - The Implementation Plan (Decomposed and Prioritized Task List)

## [ ] Task 1: 在 settings.py 补齐 uvicorn 与日志相关的集中配置项
- **Priority**: high
- **Depends On**: None
- **Description**: 
  - 扩展 `master/core/settings.py` 中的 `Settings` 类，新增/规范化以下字段并设置默认值：
    - uvicorn 行为：`host: str`、`port: int`、`reload: bool`、`access_log: bool`、`workers: int`
    - 日志级别：`log_level: str`（DEBUG/INFO/WARNING/ERROR，兼容 uvicorn）
    - 日志路径：`log_dir: str`（主日志文件绝对路径）、`uvicorn_access_log: str`、`uvicorn_error_log: str`；默认路径统一放在 `master/log/` 下，分别命名如 `master.log`、`access.log`、`error.log`，或按 Open Questions 的结论决定是否合流
    - 日志格式：`log_format: str`（默认含 asctime、name、levelname、message、process、thread 等）、`access_log_format: str`（uvicorn access 风格，含 client addr、method、path、status、time taken 等）、`log_datefmt: str`（例如 `%Y-%m-%d %H:%M:%S`）
  - 保留现有字段的向后兼容（现有 `log_dir`/`error_log_dir` 若重命名须在变更说明中明确）。
  - 在 settings 里以注释标注每个字段的用途与生效位置（业务 logger / uvicorn）。
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `programmatic` TR-1.1: 在 Python shell 中 `from master.core.settings import settings`，能访问且非空：`host`、`port`、`reload`、`access_log`、`workers`、`log_level`、`log_dir`、`uvicorn_access_log`、`uvicorn_error_log`、`log_format`、`access_log_format`、`log_datefmt`。
  - `programmatic` TR-1.2: 所有路径字段均为绝对路径（`os.path.isabs` 为 True），且指向同一个父目录。
  - `programmatic` TR-1.3: `log_level` 取值属于 logging._nameToLevel 中已知名称之一（大小写不敏感，最终统一大写）。
  - `human-judgement` TR-1.4: 字段命名自解释、注释清楚，无需翻阅代码即能理解。
- **Notes**: 路径统一放在 `master/log/` 目录（由 MASTER_DIR 推导），避免 scripts 层再产生另一套路径。

## [ ] Task 2: 在 logging.py 新增 build_uvicorn_log_config 工具函数并去重 handler
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - 在 `master/core/logging.py` 中新增函数 `build_uvicorn_log_config(settings) -> dict`，返回一个符合 uvicorn `LOGGING_CONFIG` schema 的 dict，至少包含 version、disable_existing_loggers、formatters、handlers、loggers（uvicorn / uvicorn.error / uvicorn.access）。
  - formatters 中使用 `settings.log_format` + `settings.log_datefmt` 生成 `default` formatter；access formatter 用 `settings.access_log_format` + `settings.log_datefmt`。
  - handlers 至少包含：
    - `default`（写到 `settings.log_dir`，级别=`settings.log_level`）
    - `access`（写到 `settings.uvicorn_access_log` 或合流，级别=INFO 或 settings.log_level）
    - `error`（写到 `settings.uvicorn_error_log` 或合流，级别=WARNING）
  - handler 选型：可复用当前 `AsyncFileHandler` 封装一个工厂，或暂时使用标准 `FileHandler`（文件注释中标注未来可替换）。
  - 幂等处理：改造现有的 `setup_logging(settings)`，在内部记录/检查是否已挂载同一路径 handler，避免重复；同时 `build_uvicorn_log_config` 返回的 dict 中 `disable_existing_loggers=False`，保证 setup_logging 预挂 handler 不被清除。
  - 新增/完善 docstring，说明返回 dict schema、与 `setup_logging` 的协作关系。
- **Acceptance Criteria Addressed**: AC-2, AC-4, AC-6
- **Test Requirements**:
  - `programmatic` TR-2.1: 调用 `build_uvicorn_log_config(settings)` 返回 dict 且包含 keys: `version`, `disable_existing_loggers`, `formatters`, `handlers`, `loggers`；loggers 中存在 `uvicorn`、`uvicorn.error`、`uvicorn.access`。
  - `programmatic` TR-2.2: formatters 中的 format 字符串与 settings 中字段完全匹配（通过 assertIn 校验占位符/关键字段）。
  - `programmatic` TR-2.3: handlers 的 file 输出路径等于 settings 中对应字段（`log_dir` / `uvicorn_access_log` / `uvicorn_error_log` 或其合流决定）。
  - `programmatic` TR-2.4: 在同一进程内 `setup_logging(settings)` 连续调用 2 次后，`logging.getLogger().handlers` 中指向同一文件路径的 handler 数量不超过 1（幂等）。
  - `programmatic` TR-2.5: 写入一条测试日志到 `logging.getLogger("uvicorn.error")`，目标文件出现该条且仅出现 1 次。
- **Notes**: 若最终决定 access/error 合流到主日志，需在 handler 上配置合适的 level/filter，避免 access 淹没错误。

## [ ] Task 3: 改造 master/main.py 让直接启动使用 settings + 统一 log_config
- **Priority**: high
- **Depends On**: Task 2
- **Description**:
  - 在 `master/main.py` `__main__` 分支中，把 uvicorn 启动参数全部替换为来自 `settings` 的取值：`host=settings.host`, `port=settings.port`, `reload=settings.reload`, `access_log=settings.access_log`, `workers=settings.workers`。
  - 新增 `log_config=build_uvicorn_log_config(settings)` 传入 `uvicorn.Config(...)`。
  - 确保 `setup_logging(settings)` 在 uvicorn 之前调用，但与 Task 2 的幂等/去重协同工作，避免双倍日志。
  - 启动后（lifespan 中或 uvicorn 启动前）logger 打印一条包含实际日志路径的 INFO，例如 `Logging configured: main=%s access=%s error=%s`（用于肉眼核对）。
  - 保持现有 sys.path 处理、lifespan、路由、gRPC、CORS 逻辑不变。
- **Acceptance Criteria Addressed**: AC-2, AC-4, AC-5, AC-6
- **Test Requirements**:
  - `programmatic` TR-3.1: 以 `python -m master.main` 启动（可用子进程跑 3s 后 kill），检查：日志文件被创建于 settings 指定路径、日志行格式符合 settings.log_format、出现包含 "Logging configured" 的行。
  - `programmatic` TR-3.2: 直接启动后 HTTP GET `/` 被服务端处理（可 curl），`uvicorn.access` 对应日志行写入 `settings.uvicorn_access_log` 或合流文件，且格式匹配 `access_log_format`。
  - `programmatic` TR-3.3: 监听端口等于 `settings.port`，host 监听行为与 `settings.host` 一致（可从 netstat/ss 或连接 0.0.0.0 能力验证）。
  - `programmatic` TR-3.4: 同一日志记录在日志文件仅出现一次（检查 "应用启动完成" 等特征行）。
- **Notes**: 对于子进程测试需确保清理日志文件与进程，避免污染后续。

## [ ] Task 4: 改造 scripts/start.sh 使 Master 启动复用同一配置，不再 shell 层重定向到异路径日志
- **Priority**: high
- **Depends On**: Task 3
- **Description**:
  - 修改 `scripts/start.sh` 中的 `start_master`：
    1. 移除或重新定义 shell 变量 `MASTER_LOG`：若保留，其值必须等于 settings 中的主日志文件路径（可通过 `python -c` 读取 settings.log_dir 来赋值，避免硬编码）。
    2. 替换当前的 `nohup bash -c "$actual_cmd" > "$MASTER_LOG" 2>&1 &`：改为：
       - 方案 A（推荐）：写一个最小启动入口（可内联在 `-c`），即复用 `master/main.py` 的 `__main__` 等价代码：导入 settings、传入 log_config 后调用 uvicorn Server，从而保证与直接启动完全一致。具体命令：`cd $PROJECT_ROOT && uv run python -m master.main`（此时 main.py 的 __main__ 分支负责一切），必要时不再用 `python -m uvicorn main:app ...`。
       - 方案 B：若保留 `-m uvicorn`，必须通过 `--log-config` 传入 json/yaml 路径或动态生成 dict 的方式；但 dict 方式不便命令行传参，故优先方案 A。
    3. 移除脚本内部的 HOST/PORT 默认值回退逻辑（`local master_host="${HOST:-0.0.0.0}"` 等），或改为仅在 settings 自身支持 env 覆盖时使用相同 env 名（pydantic-settings 自动大写），且脚本日志打印处使用 settings 的值。
  - 脚本中健康检查端口号来源：使用 `python -c` 读取 `settings.port`，确保与实际监听一致。
  - 脚本打印的“日志文件: xxx”改为输出真实 settings 中的主日志路径（读自 settings.log_dir）。
  - 保证 `nohup` 仅把 Python 崩溃级的 stdout/stderr 输出到合理位置（可写到与 settings.log_dir 同目录的 `.nohup.out` 或 `/dev/null`，由实现决定，但禁止写与 settings 不同的主日志）。
- **Acceptance Criteria Addressed**: AC-3, AC-5, AC-7, AC-8
- **Test Requirements**:
  - `programmatic` TR-4.1: 干净环境（`rm -rf master/log/* logs/*`），执行 `scripts/start.sh start master --no-wait`，等待健康检查通过后：检查 `master/log/` 下存在 settings 配置的日志文件，且 `logs/master.log` **未被创建**（或大小=0）。
  - `programmatic` TR-4.2: 触发一次请求与业务日志后，脚本启动产生的日志行格式（asctime/name/levelname 模式）与直接启动产生的日志行格式逐字段匹配成功（比对 regex/模板，忽略具体时间与值）。
  - `programmatic` TR-4.3: 实际监听 port 等于 `python -c 'from master.core.settings import settings; print(settings.port)'` 的输出；在未设置 HOST/PORT env 时，不等于脚本旧硬编码 `5500` 的“巧合”值应验证逻辑：在 settings 改默认 port 为其他值后重启，脚本启动应监听新端口。
  - `programmatic` TR-4.4: 脚本 stdout 中存在形如 `日志文件: <path>` 的行，其中 `<path>` 与 settings.log_dir 的绝对路径完全一致。
  - `programmatic` TR-4.5: 执行 `scripts/stop.sh stop master` 后，PID 文件清理、端口释放；日志文件末尾包含“优雅停机”或类似结束标记（可 grep 关键字）。
- **Notes**: 为避免破坏 start.sh 其它部分（worker、all），仅修改 `start_master` 与脚本局部辅助函数；worker 逻辑不动。

## [ ] Task 5: 一致性综合验证 + 文档性注释补充
- **Priority**: medium
- **Depends On**: Task 4
- **Description**:
  - 在 settings.py 顶部或相关字段附近，加一段简短注释说明：日志与 uvicorn 启动的"两处入口"（直接运行 main.py、scripts/start.sh）均会读取这些字段。
  - 在 scripts/start.sh 的 `start_master` 函数上方加注释说明：启动路径已收敛到 `python -m master.main`，其配置来源是 settings 而非本 shell 变量。
  - 进行一次人工的一致性回归（两种启动方式下的日志对比、端口、access 格式），最终确认无异。
- **Acceptance Criteria Addressed**: AC-1, AC-3, AC-4, AC-8
- **Test Requirements**:
  - `human-judgement` TR-5.1: settings.py 与 start.sh 中确实存在对应注释说明，开发新成员读之能理解"单一真相来源"。
  - `programmatic` TR-5.2: 两种方式产生的 access 日志，对同一请求（相同 method/path/status 行）正则匹配一致；业务日志关键行同样一致（可在测试脚本中做等价正则判定）。
- **Notes**: 本任务偏 polish；若前序任务均通过，本任务成本较低。若发现 AC-3/AC-4 仍有瑕疵，须回到 Task 2–4 微调。
