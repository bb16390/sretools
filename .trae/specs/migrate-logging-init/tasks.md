# Tasks
- [ ] Task 1: 在 `master/core/logging.py` 中新增 `setup_logging(settings)` 函数
  - [ ] SubTask 1.1: 补充 `os`、`logging`、`FileHandler` 等必要导入（如当前文件未导入）
  - [ ] SubTask 1.2: 实现 `setup_logging(settings)`，迁移以下逻辑：
        - 创建 `settings.log_dir` 父目录
        - 创建 `utf-8` 编码的 `FileHandler`，级别取自 `settings.log_level`
        - 用 `AsyncFileHandler` 包装 `FileHandler`
        - 配置 `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'` formatter
        - 设置根 logger 级别并添加 `async_file_handler`
  - [ ] SubTask 1.3: 对根 logger 做去重处理，避免重复调用堆叠 handler
- [ ] Task 2: 调整 `master/main.py` 调用方
  - [ ] SubTask 2.1: 将导入改为 `from master.core.logging import AsyncFileHandler, setup_logging`
  - [ ] SubTask 2.2: 删除 main.py 第 94-113 行内联日志初始化代码
  - [ ] SubTask 2.3: 在原位置调用 `setup_logging(settings)`
  - [ ] SubTask 2.4: 清理仅服务于被删除代码的顶层导入（如 `FileHandler` 若已无其他引用）
- [ ] Task 3: 验证
  - [ ] SubTask 3.1: 运行 `python -c "from master.main import app"` 或 `python -m master.main` 相关导入校验，确认无语法/导入错误
  - [ ] SubTask 3.2: 确认日志目录按 `settings.log_dir` 正常创建，根 logger 仅含一个 `async_file_handler`

# Task Dependencies
- [Task 2] 依赖 [Task 1] 完成（需要 `setup_logging` 函数已存在）
- [Task 3] 依赖 [Task 2] 完成
