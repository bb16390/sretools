# 修复 Master 程序启动后未记录请求（access log）

## 任务背景

用户反馈：master 程序启动后，HTTP 请求日志（access log）未被记录。
本计划在已完成的现象调查基础上，给出根因结论与最小可行的修复方案。

---

## 一、根因分析（Phase 1 探索结论）

### 1. 当前 access log 流向

| 环节 | 文件 / 位置 | 行为 |
|---|---|---|
| uvicorn 发起 access log | `uvicorn/protocols/http/h11_impl.py:479-487` | `access_logger.info('%s - "%s %s HTTP/%s" %d', client_addr, method, path, http_version, status)` |
| `uvicorn.access` logger 配置 | `uvicorn/config.py:69-100` 默认 `LOGGING_CONFIG` | handler=`access`(StreamHandler→**stdout**)，`propagate=False` |
| 项目自身日志配置 | [master/core/logging.py:152-176](file:///workspace/master/core/logging.py) `setup_logging()` | 仅向 **root logger** 加 `AsyncFileHandler`；**未触碰 `uvicorn.*` logger** |
| 启动重定向 | [scripts/start.sh:309](file:///workspace/scripts/start.sh#L309) | `nohup bash -c "$actual_cmd" >> "$MASTER_LOG" 2>&1 &` |

由于 `uvicorn.access.propagate=False`，access log **不会**进入 root 的 `AsyncFileHandler`，
只能经 uvicorn 自带 `StreamHandler` 写到 **stdout**，再靠 shell 的 `>> $MASTER_LOG 2>&1` 重定向落盘。

### 2. 根因：stdout 块缓冲

- Python 的 **stdout 在被重定向到文件时切换为“块缓冲”**（约 4~8KB 一块），而 **stderr 是无缓冲/行缓冲**。
- 因此日志文件中：
  - uvicorn 启动信息（`Started server process` / `Application startup complete`，走 **stderr**）**立即出现**；
  - 应用业务日志（走 root → `AsyncFileHandler`，自带 0.2s 批量刷盘）**及时出现**；
  - **access log（走 stdout）被块缓冲拦住**，要等缓冲区满、进程退出或其它 stdout 写入触发 flush 才落盘。
- 现场证据：[master/log/uvicorn.log](file:///workspace/master/log/uvicorn.log) 共 200 行，仅末行 `INFO: 127.0.0.1:42170 - "GET / HTTP/1.1" 307 Temporary Redirect` 是 access log（启动脚本健康检查那一条），其能出现是被紧随其后的 gRPC `print("✅ ...")` 触发 flush 所致。**正常运行中持续来的请求 access log 会滞留在 stdout 缓冲区**，实时 `tail` 看不到 → 表现为“启动后未记录请求”。

### 3. 关键顺序确认（决定修复可行性）

`uvicorn.Config.__init__`（[config.py:280](file:///workspace/.venv/lib/python3.12/site-packages/uvicorn/config.py#L280)）调用 `configure_logging()` → `dictConfig(LOGGING_CONFIG)`，
**先于** `Config.load()`（[server.py:86](file:///workspace/.venv/lib/python3.12/site-packages/uvicorn/server.py#L86)）→ `import_from_string("main:app")` → 触发 [master/main.py:85](file:///workspace/master/main.py#L85) `setup_logging(settings)`。

 ⇒ **在 `setup_logging()` 内重新配置 `uvicorn.*` logger，会覆盖 uvicorn 默认配置且后续不会被再次覆盖**（`configure_logging` 仅在 `__init__` 调用一次）。

### 4. 顺带发现：死代码

[scripts/start.sh:290-296](file:///workspace/scripts/start.sh#L290-L296) 的 `launch_cmd` 变量带 `access_log=False` 但从未被使用（实际生效的是 [L301-L305](file:///workspace/scripts/start.sh#L301-L305) 的 `actual_cmd`），易让人误以为 access log 被关闭。

---

## 二、修复方案

**核心思路：让 access log 不再走 stdout，改走 root logger 的 `AsyncFileHandler`**（与业务日志同一通道，0.2s 批量刷盘，可靠落盘），从根上消除 stdout 块缓冲问题。

uvicorn 的 access 记录 `msg='%s - "%s %s HTTP/%s" %d'`、`args=(client_addr, method, path, http_version, status)`，
标准 `Formatter` 的 `getMessage()` 即 `msg % args`，可正确渲染为 `127.0.0.1:42170 - "GET / HTTP/1.1" 307`，
**无需引入 uvicorn 的 `AccessFormatter`**，格式与业务日志一致。

### 变更 1：在 `setup_logging()` 中接管 `uvicorn.*` logger（核心修复）

- **文件**: [master/core/logging.py](file:///workspace/master/core/logging.py)
- **位置**: `setup_logging()` 末尾（`root_logger.addHandler(async_file_handler)` 之后）
- **做什么**: 遍历 `("uvicorn", "uvicorn.error", "uvicorn.access")`，清空各自 handler，置 `propagate=True`，按 `settings.log_level` 设置级别。
- **为什么**: 去掉 uvicorn 自带的 `StreamHandler`(stdout/stderr)，让所有 uvicorn 日志（含 access）向上传播到 root 的 `AsyncFileHandler`，统一走文件、统一刷盘，消除 stdout 块缓冲。
- **怎么做**: 在 `setup_logging()` 末尾追加：
  ```python
  # 接管 uvicorn 日志：清除其自带 StreamHandler（stdout/stderr），
  # 改由 root logger 的 AsyncFileHandler 统一写入，避免 stdout 块缓冲导致 access log 滞留。
  # 注意：setup_logging 在 app 导入期执行，晚于 uvicorn Config.__init__ 的 dictConfig，故此覆盖最终生效。
  for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
      _uv_logger = logging.getLogger(_name)
      _uv_logger.handlers = [h for h in _uv_logger.handlers if isinstance(h, AsyncFileHandler)]
      _uv_logger.propagate = True
      _uv_logger.setLevel(getattr(logging, settings.log_level))
  ```
  > 说明：用 `isinstance(h, AsyncFileHandler)` 过滤而非 `handlers = []`，是为了保证 `setup_logging` 被多次调用（如热重载二次导入）时不重复叠加 handler，同时清掉 uvicorn 的 StreamHandler。`propagate=True` 使记录传到 root → `AsyncFileHandler`。
- **行为变化（预期）**:
  - access log 行格式由 `INFO:     127.0.0.1:... - "GET / HTTP/1.1" 307 Temporary Redirect`
    变为 `2026-08-11 09:49:23,695 - uvicorn.access - INFO - 127.0.0.1:... - "GET / HTTP/1.1" 307`（与业务日志同格式，无状态码短语、无颜色）。
  - uvicorn 启动/停机信息（原走 stderr）也改走 `AsyncFileHandler`，仍落同一文件。
  - 不再依赖 shell 的 `>> $MASTER_LOG 2>&1` 重定向来捕获 access log（重定向仍保留，用于捕获 `print()` 等直写 stdout 的输出）。

### 变更 2：启动脚本设置 `PYTHONUNBUFFERED=1`（兜底加固）

- **文件**: [scripts/start.sh](file:///workspace/scripts/start.sh)
- **位置**: `start_master()` 中 `nohup bash -c "$actual_cmd" >> "$MASTER_LOG" 2>&1 &` 之前
- **做什么**: 在 `actual_cmd` 的执行环境注入 `PYTHONUNBUFFERED=1`（即 `actual_cmd="export PYTHONUNBUFFERED=1; cd '$MASTER_DIR' && uv run python -m uvicorn main:app ..."`，或直接 `PYTHONUNBUFFERED=1 nohup ...`）。
- **为什么**: 变更 1 已让 access log 不走 stdout，但仍有少量 `print()`（如 [master/grpc/server.py](file:///workspace/master/grpc/server.py) 的 `print("[gRPC] Worker ...")`、`print("✅ Master gRPC Server started ...")`）直写 stdout，重定向时同样受块缓冲影响。`PYTHONUNBUFFERED=1` 强制 stdout/stderr 行缓冲，作为兜底确保这些输出也能及时落盘。
- **怎么做**: 将 [scripts/start.sh:301-305](file:///workspace/scripts/start.sh#L301-L305) 的两条 `actual_cmd` 分支行首加 `PYTHONUNBUFFERED=1 `，例如：
  ```bash
  if command -v uv &> /dev/null; then
      actual_cmd="cd '$MASTER_DIR' && PYTHONUNBUFFERED=1 uv run python -m uvicorn main:app --host '${master_host}' --port ${master_port}"
  else
      actual_cmd="cd '$MASTER_DIR' && PYTHONUNBUFFERED=1 PYTHONPATH='${MASTER_DIR}:${PROJECT_ROOT}' '${python_cmd}' -m uvicorn main:app --host '${master_host}' --port ${master_port}"
  fi
  ```

### 变更 3：清理 `launch_cmd` 死代码

- **文件**: [scripts/start.sh](file:///workspace/scripts/start.sh)
- **位置**: [L289-L299](file:///workspace/scripts/start.sh#L289-L299)
- **做什么**: 删除未被使用的 `launch_cmd` 变量及其上方“关键：从 PROJECT_ROOT 启动…”与下方“实际上直接用 uvicorn module 方式…”两段过渡注释，仅保留 `actual_cmd` 一条启动路径。
- **为什么**: `launch_cmd` 内含 `access_log=False`，与实际行为相悖，是本次“以为 access log 被关”误判的源头之一；删除以绝后患。

---

## 三、假设与决策

- **假设 1**：uvicorn 使用默认 `LOGGING_CONFIG`，项目未通过 `log_config=` 或 `dictConfig` 覆盖。已通过 [master/main.py](file:///workspace/master/main.py)、[master/core/logging.py](file:///workspace/master/core/logging.py) 全文确认。
- **假设 2**：`setup_logging()` 在 app 导入期执行，晚于 `uvicorn.Config.__init__` 的 `dictConfig`；`configure_logging()` 不会再次被调用。已通过 [uvicorn/config.py:280](file:///workspace/.venv/lib/python3.12/site-packages/uvicorn/config.py#L280) 与 [uvicorn/server.py:86](file:///workspace/.venv/lib/python3.12/site-packages/uvicorn/server.py#L86) 确认调用顺序。
- **假设 3**：标准 `Formatter` 的 `getMessage()`（`msg % args`）可正确渲染 uvicorn access 记录。已通过 [uvicorn/protocols/http/h11_impl.py:479-487](file:///workspace/.venv/lib/python3.12/site-packages/uvicorn/protocols/http/h11_impl.py#L479-L487) 的 `msg`/`args` 形态确认。
- **决策 1**：选择“接管 `uvicorn.*` logger → 统一走 `AsyncFileHandler`”而非“仅设 `PYTHONUNBUFFERED`”。前者从架构上消除双通道与 stdout 缓冲隐患，单一通道、格式一致、刷盘可靠；后者作为兜底一并保留。
- **决策 2**：access log 格式由 uvicorn 专有格式改为与业务日志一致的标准格式（无状态码短语、无颜色）。可接受，且更利于后续 grep/分析。
- **范围界定**：本计划仅解决 **HTTP access log**。gRPC 请求目前无内置 access 日志（[master/grpc/server.py](file:///workspace/master/grpc/server.py) 仅 `print`），不在本次范围；如需可后续单独加 gRPC 拦截器日志。

---

## 四、验证步骤

1. **静态检查**：
   - 阅读 [master/core/logging.py](file:///workspace/master/core/logging.py) `setup_logging()` 末尾，确认新增 `uvicorn.*` 接管逻辑存在且 `propagate=True`。
   - 阅读 [scripts/start.sh](file:///workspace/scripts/start.sh) `start_master()`，确认仅剩 `actual_cmd` 一条路径，含 `PYTHONUNBUFFERED=1`，未传 `--no-access-log`，`launch_cmd` 已删除。

2. **清空旧日志并启动**：
   ```bash
   : > /workspace/master/log/uvicorn.log
   ./scripts/start.sh start master --skip-deps --no-wait
   ```
   确认 master 进程存活（`./scripts/start.sh status` 或 `cat /workspace/.pids/master.pid`）。

3. **触发请求并实时观察**（关键：验证不再延迟）：
   ```bash
   # 终端 A：实时 tail
   tail -f /workspace/master/log/uvicorn.log
   # 终端 B：连发 3 次请求
   for i in 1 2 3; do curl -s -o /dev/null http://127.0.0.1:5500/; sleep 1; done
   ```
   - 预期：终端 A 在每次请求后 **0.2s 内**出现一行形如
     `2026-... - uvicorn.access - INFO - 127.0.0.1:... - "GET / HTTP/1.1" 307`
     共 3 条，且不再被成块刷出。
   - 反例（修复前）：3 条 access log 滞后数秒甚至不出现，直到缓冲区满。

4. **格式一致性**：确认 access log 行与业务日志行（如 `应用启动完成`）使用相同的时间戳/name/level 前缀。

5. **无重复**：确认每个请求只出现 **1 行** access log（`propagate=True` 但 `uvicorn.access` 自身 handler 已清空，仅 root 的 `AsyncFileHandler` 写一次）。

6. **兜底验证**：确认 gRPC 启动的 `✅ Master gRPC Server started ...` 这类 `print()` 输出也在日志中及时出现（验证 `PYTHONUNBUFFERED=1` 生效）。

7. **停机清理**：`./scripts/start.sh stop master`，确认优雅停机日志写入文件。
