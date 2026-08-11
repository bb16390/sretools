# Tasks

- [x] Task 1: 在 `master/core/settings.py` 中新增 `log_format` 字段
  - [x] SubTask 1.1: 在 `Settings` 类的日志配置区域（`log_level`/`log_dir`/`error_log_dir` 附近）新增 `log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'`
  - [x] SubTask 1.2: 确认字段默认值与 `logging.py` 中当前硬编码的格式字符串完全一致

- [x] Task 2: 修改 `master/core/logging.py` 使用 `settings.log_format`
  - [x] SubTask 2.1: 将 `setup_logging` 中的 `logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')` 改为 `logging.Formatter(settings.log_format)`
  - [x] SubTask 2.2: 确认其余逻辑（目录创建、FileHandler 编码、AsyncFileHandler 包装、根 logger 去重）不变

- [x] Task 3: 修改 `scripts/start.sh` master 日志路径从 settings.py 读取
  - [x] SubTask 3.1: 新增 `get_master_log_file()` 函数，通过 Python 读取 `settings.log_dir`，失败时回退到 `$MASTER_DIR/log/uvicorn.log`
  - [x] SubTask 3.2: 将 `MASTER_LOG` 变量从硬编码 `$LOG_DIR/master.log` 改为调用 `get_master_log_file` 的返回值
  - [x] SubTask 3.3: 在 `start_master` 中重定向前通过 `mkdir -p "$(dirname "$MASTER_LOG")"` 创建日志目录
  - [x] SubTask 3.4: 将 `nohup` 重定向从 `> "$MASTER_LOG"` 改为 `>> "$MASTER_LOG"`（追加模式，与 FileHandler 的 append 模式一致）
  - [x] SubTask 3.5: 保留 `LOG_DIR`/`WORKER_LOG` 不变（worker 不在本次范围）
  - [x] SubTask 3.6: 更新 `show_status()` 中 master 日志路径的展示，使用 `$MASTER_LOG` 而非 `$LOG_DIR`

- [x] Task 4: 修改 `scripts/stop.sh` 状态展示使用一致的 master 日志路径
  - [x] SubTask 4.1: 新增与 `start.sh` 一致的 `get_master_log_file()` 函数（或复用相同逻辑）
  - [x] SubTask 4.2: 更新 `show_status()` 中 master 日志路径的展示，使用从 settings 读取的路径

- [x] Task 5: 验证
  - [x] SubTask 5.1: 运行 `python -c "from master.core.settings import settings; print(settings.log_format, settings.log_dir)"` 确认配置可读
  - [x] SubTask 5.2: 运行 `python -c "from master.core.logging import setup_logging; from master.core.settings import settings; setup_logging(settings); import logging; logging.getLogger().info('test')"` 确认日志写入正常
  - [x] SubTask 5.3: 执行 `bash scripts/start.sh status` 确认 master 日志路径展示正确
  - [x] SubTask 5.4: 确认脚本与直接启动 `python -m master.main` 时，日志文件路径一致（均为 `settings.log_dir`）

# Task Dependencies
- [Task 2] 依赖 [Task 1] 完成（需要 `settings.log_format` 字段已存在）
- [Task 3] 和 [Task 4] 独立于 [Task 1]/[Task 2]，可并行开发
- [Task 5] 依赖 [Task 1]–[Task 4] 全部完成
