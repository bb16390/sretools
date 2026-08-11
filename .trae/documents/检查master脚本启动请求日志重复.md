# 检查 Master 经 scripts 启动时是否会重复记录请求日志

## 任务背景

用户希望确认：当 master 通过 `scripts/start.sh` 启动时，HTTP 请求日志（access log）是否会被重复记录（同一条请求被写入两次或更多）。

## 现状分析（Phase 1 探索结论）

### 1. 启动命令实际形态

[scripts/start.sh](file:///workspace/scripts/start.sh#L300-L309) 中 `start_master` 函数有两段命令字符串：

- **`launch_cmd`**（[L293-L296](file:///workspace/scripts/start.sh#L293-L296)）：通过 `python -c` 内联方式启动，**显式传入 `access_log=False`**。
- **`actual_cmd`**（[L301-L305](file:///workspace/scripts/start.sh#L301-L305)）：使用 `python -m uvicorn main:app --host ... --port ...`，**未传 `--no-access-log` / `--access-log`**。

实际生效的是 `actual_cmd`（[L309](file:///workspace/scripts/start.sh#L309) 执行 `nohup bash -c "$actual_cmd" >> "$MASTER_LOG" 2>&1 &`）。`launch_cmd` 是 **dead code**，从未被使用。

结论：脚本启动时 uvicorn 的 `access_log` 走默认值 `True`，**会输出 access log**。

### 2. stdout/stderr 重定向目标

- `MASTER_LOG = $(get_master_log_file)`（[L307](file:///workspace/scripts/start.sh#L307)）
- `get_master_log_file`（[L123-L141](file:///workspace/scripts/start.sh#L123-L141)）从 `master.core.settings.settings.log_dir` 读取
- `settings.log_dir` 默认值 = `os.path.join(MASTER_DIR, "log", "uvicorn.log")`（[master/core/settings.py#L38](file:////workspace/master/core/settings.py#L38)）

`nohup ... >> "$MASTER_LOG" 2>&1 &` 把 uvicorn 进程的 stdout/stderr 一并追加到该文件。

### 3. 应用内日志系统

[master/main.py](file:///workspace/master/main.py#L85) 在模块加载时调用 `setup_logging(settings)`：

- [master/core/logging.py#L152-L176](file:///workspace/master/core/logging.py#L152-L176) 创建 `FileHandler(settings.log_dir, encoding='utf-8')`，包装为 `AsyncFileHandler`，**添加到根 logger**。
- 该 FileHandler 写入的目标文件 = `settings.log_dir` = **与 `MASTER_LOG` 同一个文件**。

### 4. uvicorn 默认日志配置（关键）

uvicorn 默认 `LOGGING_CONFIG`（未在项目内覆盖）：

| Logger | Handler | propagate |
|---|---|---|
| `uvicorn` | StreamHandler → stderr | **False** |
| `uvicorn.error` | 无（继承 uvicorn） | True（向 uvicorn 传播，uvicorn 不再向 root 传播） |
| `uvicorn.access` | StreamHandler → stdout | **False** |

项目内 `setup_logging` **未对 `uvicorn.*` logger 做任何配置**，也未调用 `dictConfig` 覆盖 uvicorn 默认配置；仅向 root logger 加了一个 `AsyncFileHandler`。

### 5. 请求日志流向追踪

一次 HTTP 请求到达，uvicorn 通过 `uvicorn.access` logger 发出一条 INFO 记录：

1. `uvicorn.access` logger 自身 handler 写入 stdout → 被 `nohup >>` 重定向到 `MASTER_LOG` 文件。
2. 因 `propagate=False`，**不会**向 root logger 传播 → `AsyncFileHandler` **不会**再写一次。

结果：**每个请求的 access log 只写入文件 1 次**。

### 6. 应用日志（非请求日志）流向

`logger = logging.getLogger(__name__)`（`master.main`、`master.apps.*` 等）发出的日志：

1. `master.main` logger 无自身 handler，propagate=True → 向 root 传播。
2. root logger 仅有 `AsyncFileHandler` → 写入 `settings.log_dir`（= `MASTER_LOG`）。
3. root logger **未配置 StreamHandler**，所以应用日志不会进 stdout/stderr，不会被 `nohup` 重定向再次写入。

结果：**应用日志也只写入文件 1 次**。

## 结论

**Master 经 `scripts/start.sh` 启动时，请求日志（access log）不会重复记录。** 

- `uvicorn.access` 因 `propagate=False` 仅由 uvicorn 自带 StreamHandler 写一次（经 stdout 重定向到文件）。
- 应用的 `AsyncFileHandler` 因 `propagate=False` 阻断，收不到 access log，不会重复写。
- 应用业务日志则只通过 root logger 的 `AsyncFileHandler` 写一次。

## 顺带发现的潜在问题（非请求日志重复，但建议关注）

### 问题 A：`launch_cmd` 死代码引人误解
[scripts/start.sh#L290-L296](file:///workspace/scripts/start.sh#L290-L296) 定义了带 `access_log=False` 的 `launch_cmd` 但从未使用，读代码者易误以为 access log 已关闭。建议删除该段死代码，避免维护歧义。

### 问题 B：同一文件被两条写入通道共用
`MASTER_LOG`（uvicorn stdout/stderr 重定向）与 `AsyncFileHandler`（Python FileHandler）写入同一物理文件。虽然不是“重复记录同一条日志”，但：
- 两个通道各自缓冲、各自 `write()`/`flush()`，**日志行可能交错**（access log 行穿插在应用日志行之间）。
- AsyncFileHandler 有内部队列与批处理，写入时机相对滞后。

如果希望日志行严格时序一致，可考虑让 uvicorn 与 root logger 共用同一 handler（例如禁用 uvicorn 自带 handler，把 `uvicorn.access` propagate 改为 True，让其也走 `AsyncFileHandler`）。但这会改变现有行为，**不在本任务范围内**，仅作为可选优化提示。

### 问题 C：直接 `python main.py` 启动时 access_log=True
[master/main.py#L220](file:///workspace/master/main.py#L220) `if __name__ == "__main__"` 分支显式 `access_log=True`，与脚本启动行为一致，无差异。但与已废弃的 `launch_cmd` 中 `access_log=False` 意图相悖，进一步说明 `launch_cmd` 是历史遗留。

## 建议的修复动作（可选，最小改动）

仅清理死代码，**不改变日志行为**（避免引入新风险）：

- 删除 [scripts/start.sh#L290-L296](file:///workspace/scripts/start.sh#L290-L296) 的 `launch_cmd` 变量及其注释。
- 同步删除 [L298-L299](file:///workspace/scripts/start.sh#L298-L299) 关于“实际上直接用 uvicorn module 方式”的过渡注释，使启动命令来源单一清晰。

## 验证步骤

1. 阅读修改后的 `scripts/start.sh`，确认仅保留 `actual_cmd` 一条启动路径，且未传 `--no-access-log`。
2. 启动 master：`./scripts/start.sh start master --skip-deps`。
3. 触发一次 HTTP 请求：`curl http://127.0.0.1:5500/`。
4. 查看 `master/log/uvicorn.log`，确认每个请求只出现 **1 行** access log（形如 `INFO: 127.0.0.1:... - "GET / HTTP/1.1" 307 ...`）。
5. 确认应用业务日志（如“应用启动完成”）也只出现 1 次。

## 假设与决策

- **假设**：uvicorn 使用默认 `LOGGING_CONFIG`，项目未通过 `log_config=` 参数或 `dictConfig` 覆盖。已通过 [master/main.py](file:///workspace/master/main.py) 与 [master/core/logging.py](file:///workspace/master/core/logging.py) 全文确认。
- **假设**：`uvicorn.access` 默认 `propagate=False`。这是 uvicorn 官方默认 `LOGGING_CONFIG` 的既定行为（项目内未修改）。
- **决策**：本任务结论为“不会重复”，因此**不需要任何代码改动**。仅可选地清理 `launch_cmd` 死代码以避免后续误解。是否执行清理动作，由用户确认。
