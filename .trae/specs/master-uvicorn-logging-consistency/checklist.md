# Master Uvicorn 日志配置一致性 - 验证清单

## Settings 配置字段检查
- [ ] Checkpoint 1: `master/core/settings.py` 的 `Settings` 类中存在 `uvicorn_reload`、`uvicorn_workers`、`uvicorn_access_log` 三个 uvicorn 运行参数字段，类型正确且有默认值
- [ ] Checkpoint 2: `Settings` 类中存在 `log_format` 与 `access_log_format` 两个日志格式字段，并带有合理默认格式字符串
- [ ] Checkpoint 3: 日志文件路径（应用/错误/access）字段语义清晰，其解析后的绝对路径全部位于 `$PROJECT_ROOT/logs/` 目录下（与 scripts 的 LOG_DIR 一致）
- [ ] Checkpoint 4: Settings 实例能在 Python 中无异常构造，pydantic 校验通过

## setup_logging 增强检查
- [ ] Checkpoint 5: 调用 `setup_logging(settings)` 后，`logging.getLogger("uvicorn")`、`uvicorn.error`、`uvicorn.access` 三个 logger 均已绑定至少一个 handler
- [ ] Checkpoint 6: 上述三个 logger 的级别等于 `settings.log_level`，且 formatter 使用 settings 中对应格式字符串（access logger 使用 access_log_format）
- [ ] Checkpoint 7: access log 按 settings 配置写入独立或统一文件，目录自动创建，文件内容包含 access log 行
- [ ] Checkpoint 8: 连续两次调用 `setup_logging(settings)` 后，各 logger 的 handler 数量不增加，输出日志不重复（幂等性）

## 直接启动（python -m master.main）一致性检查
- [ ] Checkpoint 9: `master/main.py` 中 `build_uvicorn_kwargs(settings)` 返回的 dict 包含 host/port/reload/workers/access_log 等键，值与 settings 对应字段完全一致
- [ ] Checkpoint 10: 直接启动 `uv run python -m master.main`，进程启动后监听的 host/port 与 settings 一致
- [ ] Checkpoint 11: 直接启动后，settings 指定的主日志文件（如 `logs/master.log`）存在且包含应用启动日志（如 `应用启动完成`）
- [ ] Checkpoint 12: 访问一次 HTTP 端点后，主日志文件中同时存在应用日志行和 uvicorn access log 行，两者格式统一，均带 asctime/name/levelname/message

## 脚本启动（scripts/start.sh）一致性检查
- [ ] Checkpoint 13: `scripts/start.sh start master --skip-deps --no-wait` 成功启动，PID 文件写入 `.pids/master.pid`
- [ ] Checkpoint 14: 脚本启动后，主日志文件路径与直接启动完全一致（均为 `logs/master.log` 或 settings 中配置的路径），不再额外依赖 shell 重定向作为主日志
- [ ] Checkpoint 15: 脚本启动后日志格式、内容、access log 写入与直接启动字节级一致（除 PID/时间戳差异）
- [ ] Checkpoint 16: start.sh 输出中提示的"日志文件: xxx"路径与 settings 实际路径一致

## 停止兼容性与其他脚本检查
- [ ] Checkpoint 17: `scripts/stop.sh stop master` 能优雅停止由 start.sh 启动的 master，PID 文件清理，无残留进程
- [ ] Checkpoint 18: `scripts/start.sh status` 展示的日志目录与实际一致，端口检测正常
- [ ] Checkpoint 19: `scripts/stop.sh` 与 `upgrade.sh`/`deploy.sh`（若引用 master）不再使用旧的日志路径或硬编码参数

## 配置集中性审计（无硬编码散落）
- [ ] Checkpoint 20: 全文搜索 master 相关代码：`log` 路径、`format` 字符串、`reload`、`access_log` 布尔值等除 settings 定义处与读取调用处外，无硬编码值（main.py 的 __main__ 分支、start.sh 命令行均不再硬编码）
- [ ] Checkpoint 21: 旧字段 `log_dir` / `error_log_dir`（若重命名）在 master 代码中的非注释引用已全部迁移，测试不报错
- [ ] Checkpoint 22: 现有测试 `pytest tests/dashboard/core/test_logging.py tests/dashboard/core/test_logging_performance.py` 全部通过

## 集成回归检查
- [ ] Checkpoint 23: 两种启动方式下 reload 行为一致（同开同关，不因 shell 而差异），uvicorn workers 数一致
- [ ] Checkpoint 24: 不再有 `master/log/uvicorn.log`（旧路径）与 `logs/master.log`（新路径）双写分裂的情况，旧路径不被创建
- [ ] Checkpoint 25: 两种方式分别启动并停止一次后，日志文件中均包含启动/关闭完整生命周期记录，无丢失关键日志
