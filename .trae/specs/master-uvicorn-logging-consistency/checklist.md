# Master Uvicorn 日志配置一致性 - 验证清单

## Settings 配置字段检查
- [ ] Checkpoint 1: `master/core/settings.py` 的 `Settings` 类中存在 `uvicorn_reload`、`uvicorn_workers`、`uvicorn_access_log` 三个 uvicorn 运行参数字段，类型正确且有默认值
- [ ] Checkpoint 2: `Settings` 类中存在 `log_format` 与 `access_log_format` 两个日志格式字段，并带有合理默认格式字符串
- [ ] Checkpoint 3: 日志文件路径（应用/错误/access）字段语义清晰，其解析后的绝对路径全部位于 `$PROJECT_ROOT/logs/` 目录下（与 scripts 的 LOG_DIR 一致）
- [ ] Checkpoint 4: Settings 实例能在 Python 中无异常构造，pydantic 校验通过
- [ ] Checkpoint 5: Settings 中存在轮转参数 `log_rotation_when`（默认 "midnight"）、`log_rotation_interval`（默认 1）、`log_backup_count`（默认 30）、`log_rotation_encoding`（默认 "utf-8"），类型与默认值均正确

## setup_logging 增强检查（含 TimedRotatingFileHandler）
- [ ] Checkpoint 6: 调用 `setup_logging(settings)` 后，`logging.getLogger("uvicorn")`、`uvicorn.error`、`uvicorn.access` 三个 logger 均已绑定至少一个 handler
- [ ] Checkpoint 7: 上述三个 logger 的级别等于 `settings.log_level`，且 formatter 使用 settings 中对应格式字符串（access logger 使用 access_log_format）
- [ ] Checkpoint 8: access log 按 settings 配置写入独立或统一文件，目录自动创建，文件内容包含 access log 行
- [ ] Checkpoint 9: 连续两次调用 `setup_logging(settings)` 后，各 logger 的 handler 数量不增加，输出日志不重复（幂等性）
- [ ] Checkpoint 10: 各 logger 绑定的 AsyncFileHandler 内部 `_file_handler` 的实际类型为 `logging.handlers.TimedRotatingFileHandler`，不再使用普通 FileHandler
- [ ] Checkpoint 11: TimedRotatingFileHandler 的 `when` / `interval` / `backupCount` / `encoding` 四个参数分别等于 settings 中的 `log_rotation_when` / `log_rotation_interval` / `log_backup_count` / `log_rotation_encoding`
- [ ] Checkpoint 12: 主日志 / access 日志 / error 日志（若独立文件）各自使用独立的 TimedRotatingFileHandler 实例，轮转互不干扰

## 按日轮转行为验证
- [ ] Checkpoint 13: 写入若干条日志后，对主日志的底层 TimedRotatingFileHandler 调用 `doRollover()`，原日志文件被归档为带日期后缀（如 `master.log.YYYY-MM-DD`）的新文件
- [ ] Checkpoint 14: 轮转后新的主日志文件为空或仅包含轮转后的内容，后续写入进入新文件；归档文件保留且编码为 utf-8 可读
- [ ] Checkpoint 15: 设置 `log_backup_count=2` 并连续触发 3 次轮转后，最旧的第 1 份归档被自动删除，最终只保留 2 份归档 + 1 份当前文件
- [ ] Checkpoint 16: 轮转期间 AsyncFileHandler 队列中仍有未写入日志时，轮转后两部分内容（归档 + 新文件）之和等于写入总条数，无丢失
- [ ] Checkpoint 17: access log（若独立文件）轮转行为与主日志一致，同样生成带日期后缀的归档

## 直接启动（python -m master.main）一致性检查
- [ ] Checkpoint 18: `master/main.py` 中 `build_uvicorn_kwargs(settings)` 返回的 dict 包含 host/port/reload/workers/access_log 等键，值与 settings 对应字段完全一致
- [ ] Checkpoint 19: 直接启动 `uv run python -m master.main`，进程启动后监听的 host/port 与 settings 一致
- [ ] Checkpoint 20: 直接启动后，settings 指定的主日志文件（如 `logs/master.log`）存在且包含应用启动日志（如 `应用启动完成`）
- [ ] Checkpoint 21: 访问一次 HTTP 端点后，主日志文件中同时存在应用日志行和 uvicorn access log 行，两者格式统一，均带 asctime/name/levelname/message

## 脚本启动（scripts/start.sh）一致性检查
- [ ] Checkpoint 22: `scripts/start.sh start master --skip-deps --no-wait` 成功启动，PID 文件写入 `.pids/master.pid`
- [ ] Checkpoint 23: 脚本启动后，主日志文件路径与直接启动完全一致（均为 `logs/master.log` 或 settings 中配置的路径），不再额外依赖 shell 重定向作为主日志
- [ ] Checkpoint 24: 脚本启动后日志格式、内容、access log 写入与直接启动字节级一致（除 PID/时间戳差异）
- [ ] Checkpoint 25: start.sh 输出中提示的"日志文件: xxx"路径与 settings 实际路径一致

## 停止兼容性与其他脚本检查
- [ ] Checkpoint 26: `scripts/stop.sh stop master` 能优雅停止由 start.sh 启动的 master，PID 文件清理，无残留进程
- [ ] Checkpoint 27: `scripts/start.sh status` 展示的日志目录与实际一致，端口检测正常
- [ ] Checkpoint 28: `scripts/stop.sh` 与 `upgrade.sh`/`deploy.sh`（若引用 master）不再使用旧的日志路径或硬编码参数
- [ ] Checkpoint 29: 停止时 `AsyncFileHandler.close()` 正常触发轮转文件句柄释放，进程退出后无残留打开的文件句柄（可通过 `/proc/<pid>/fd` 抽查）

## 配置集中性审计（无硬编码散落）
- [ ] Checkpoint 30: 全文搜索 master 相关代码：`log` 路径、`format` 字符串、`reload`、`access_log` 布尔值、`midnight`/`backupCount` 等轮转参数，除 settings 定义处与读取调用处外，无硬编码值（main.py 的 __main__ 分支、start.sh 命令行均不再硬编码）
- [ ] Checkpoint 31: 旧字段 `log_dir` / `error_log_dir`（若重命名）在 master 代码中的非注释引用已全部迁移，测试不报错
- [ ] Checkpoint 32: 现有测试 `pytest tests/dashboard/core/test_logging.py tests/dashboard/core/test_logging_performance.py` 全部通过

## 集成回归检查
- [ ] Checkpoint 33: 两种启动方式下 reload 行为一致（同开同关，不因 shell 而差异），uvicorn workers 数一致
- [ ] Checkpoint 34: 不再有 `master/log/uvicorn.log`（旧路径）与 `logs/master.log`（新路径）双写分裂的情况，旧路径不被创建
- [ ] Checkpoint 35: 两种方式分别启动并停止一次后，日志文件中均包含启动/关闭完整生命周期记录，无丢失关键日志
- [ ] Checkpoint 36: start.sh 中不再用 `nohup > file` 的 shell 重定向承载主日志；若保留重定向，其指向文件（如 stdout 辅助日志）不应再被脚本称为"主日志"，内容也不再包含重复的应用日志
