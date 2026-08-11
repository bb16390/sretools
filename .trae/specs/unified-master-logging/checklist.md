# Master 服务统一日志与启动管理 - Verification Checklist

## Settings 集中配置（AC-1）
- [ ] `master/core/settings.py` 中存在以下字段且有默认值：`host`、`port`、`reload`、`access_log`、`workers`、`log_level`、`log_dir`、`uvicorn_access_log`、`uvicorn_error_log`、`log_format`、`access_log_format`、`log_datefmt`
- [ ] 所有路径字段均为绝对路径，且父目录一致（如均在 `master/log/` 下）
- [ ] `log_level` 取值属于标准 logging 级别名称之一
- [ ] 字段有清晰注释说明用途与生效范围（业务 logger/uvicorn）

## 直接启动日志路径正确（AC-2）
- [ ] 以 `python -m master.main` 方式启动成功
- [ ] 业务日志写入 `settings.log_dir` 指定路径
- [ ] uvicorn access 日志写入 `settings.uvicorn_access_log`（或合流文件，依据设计决定）
- [ ] uvicorn error 日志写入 `settings.uvicorn_error_log`（或合流文件）
- [ ] 除上述路径外，不在其他文件产生日志（如旧的 `logs/master.log` 未被创建）

## 脚本启动与直接启动路径一致（AC-3）
- [ ] 干净环境（清空历史日志）执行 `scripts/start.sh start master` 启动成功
- [ ] 脚本启动后产生的日志文件路径（绝对路径）与直接启动完全一致
- [ ] `$PROJECT_ROOT/logs/master.log` 未被创建或大小为 0
- [ ] PID 文件正常记录于 `.pids/master.pid`

## 日志格式一致（AC-4）
- [ ] 直接启动产生的业务日志行匹配 `settings.log_format` 模板（asctime、name、levelname、message 字段齐备）
- [ ] 脚本启动产生的业务日志行模板与直接启动完全一致
- [ ] uvicorn access 日志行匹配 `settings.access_log_format` 模板
- [ ] 两种方式下 access 日志行模板完全一致
- [ ] 日志时间格式遵循 `settings.log_datefmt`

## uvicorn 参数来源统一（AC-5）
- [ ] 直接启动的监听 host/port 等于 settings.py 中配置值
- [ ] 脚本启动的监听 host/port 等于 settings.py 中配置值
- [ ] 修改 settings.py 默认 port 为非 5500 后，两种方式均监听新 port（不再回退到脚本硬编码 5500）
- [ ] 两种方式下 access_log 开关状态与 settings.access_log 一致
- [ ] 两种方式下 reload 行为与 settings.reload 一致

## 无重复日志写入（AC-6）
- [ ] 在应用中手动写入一条 logger.info，目标日志文件中该条仅出现一次
- [ ] uvicorn access 日志每行仅出现一次
- [ ] lifespan 中的 "应用启动完成" 日志仅出现一次
- [ ] 连续多次调用 setup_logging 后 handler 数量不叠加

## 脚本停止逻辑正常（AC-7）
- [ ] 脚本启动后执行 `scripts/stop.sh stop master`，master 进程退出
- [ ] 停止后 PID 文件被清理（`.pids/master.pid` 不存在）
- [ ] 停止后原监听端口已释放，可重新绑定
- [ ] 日志末尾可见 "优雅停机" 或类似结束标记，证明走了优雅路径

## 启动日志路径提示准确（AC-8）
- [ ] 执行 `scripts/start.sh start master`，stdout 中打印 "日志文件: <path>" 行
- [ ] 该打印的 path 与 `settings.log_dir` 绝对路径完全一致

## 代码质量与文档注释
- [ ] `master/core/logging.py` 中 `build_uvicorn_log_config` 有 docstring 说明输入/输出 schema
- [ ] settings.py 顶部或日志字段附近有注释说明"两处启动入口均读取此处配置"
- [ ] start.sh 的 start_master 函数上方有注释说明配置来源是 settings.py
- [ ] 未引入新的第三方依赖，pyproject.toml 无变化
