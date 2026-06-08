# Master 网关控制功能 - 产品需求文档 (PRD)

## Overview
- **Summary**: 在 Master 端实现证券交易所网关（行情网关 mdgw / 交易网关 tgw）的统一控制能力，首期支持**深交所 (SZSE)** 的 mdgw 与 tgw，同时在架构上预留**上交所 (SSE)** 和**北交所 (BJSE)** 网关控制的扩展点。提供基于 amis-admin 的管理界面 + FastAPI HTTP API，以及可插拔的核心 Python 模块（部署、启动、停止、重启、升级、回滚、状态查询）。
- **Purpose**: 统一 master 端对分布式网关二进制程序的生命周期管理，避免运维人员登录到每台机器执行脚本；同时通过抽象层为未来多交易所网关接入提供一致的接口。
- **Target Users**: 运维/DevOps 工程师、量化基础设施管理员。

## Goals
- 1) 建立可插拔的网关控制抽象层 (`GatewayControllerABC`)，定义 deploy / start / stop / restart / upgrade / rollback / status / preflight 共 8 个标准接口。
- 2) 完成深交所网关的首版实现：`mdgw` (行情网关) 与 `tgw` (交易网关) 控制器，均基于本地目录、二进制与 `cfg/config.xml` 工作模型（与 `gateway_python_dev_guide.md` 保持一致）。
- 3) 为上交所 (SSE) 与 北交所 (BJSE) 预留控制器骨架（子类 + 注册点 + NotImplementedError），后续按相同契约实现。
- 4) 提供 amis-admin 管理界面：网关实例清单 / 实例详情 / 一键启停 / 升级 / 回滚 / 查看状态。
- 5) 提供 FastAPI HTTP API，便于外部系统集成调用。
- 6) 提供单测覆盖核心抽象层和深交所控制器（mock 操作系统调用）。

## Non-Goals (Out of Scope)
- **不下发命令到远端主机执行**：首期只支持 master 进程能直接访问的本地文件系统路径；远程 SSH/Ansible 不在本期范围内。
- **不实现实盘连接 / 协议交互**：只做二进制进程/配置管理，不解析行情或交易协议。
- **不实现 gRPC 到 worker 侧的网关命令转发**；worker 侧若需网关控制，由 master 直接管理或后续再规划。
- **不实现前端独立 UI**，直接复用 `fastapi-amis-admin` 框架。
- **不重写 gRPC server 的现有逻辑**，仅在注册阶段引入新模块，与现有 WorkerService 共存。

## Background & Context
- 项目 `master/` 是一个基于 FastAPI + `fastapi-amis-admin` + gRPC 的运维工具，现有模块：`core/`（settings/logging/security/auth/globals）、`grpc/`（WorkerService）、`index/`（页面/文件上传 admin）。
- `gateway_python_dev_guide.md` 是一份详尽的网关 Python 开发指南，覆盖部署流程、升级流程、启停流程、XML 配置解析等。本次实现以该指南为契约，将零散函数重构为可测试的类模块，并在 master 中集成。
- 网关共性：目录结构为 `{install_dir}/{gateway_type}/{binary} + cfg/config.xml + (可选) server_list.xml`，监控端口在 `config.xml` 中定义。
- 进程管理：网关程序无启动脚本，通过 `subprocess.Popen` 以 `cwd=gateway_dir` 启动；PID 写入 `.{gateway_type}.pid`；优雅停止优先发送 `SIGTERM`，超时 `SIGKILL`。

## Functional Requirements
- **FR-1 抽象层**: 提供 `gateway/controllers/base.py`：`GatewayControllerABC`（抽象类，8 个接口）、`GatewayControllerRegistry`（按 `(exchange, kind)` 查找实现）。
- **FR-2 深交所 mdgw**: `gateway/controllers/szse_mdgw.py`：支持部署（解压 zip + 选模板 + 生成 config.xml）、启停（使用 pid 文件 + 监控端口就绪判断）、升级/回滚（二进制替换 + 配置备份）、状态（运行状态 / 版本 / 监控端口可达）。
- **FR-3 深交所 tgw**: `gateway/controllers/szse_tgw.py`：在 mdgw 基础上额外支持 `server_list.xml` 生成、旧版到新版的配置迁移（提取内嵌 server_list 到独立文件）。
- **FR-4 预留 SSE / BJSE**: `gateway/controllers/sse_mdgw.py`、`sse_tgw.py`、`bjse_mdgw.py`、`bjse_tgw.py` 提供骨架并在 registry 中注册占位（方法抛 `NotImplementedError`）。
- **FR-5 进程管理模块**: `gateway/core/process.py`：`GatewayProcess` 负责 start/stop/restart/status，接受 `gateway_dir`、`binary_name`、`monitor_port`、`timeout`；提供 is_running / wait_for_monitor 能力。
- **FR-6 配置与错误处理**: `gateway/core/errors.py` 定义错误码体系（Config/Binary/Process/Upgrade），`gateway/core/models.py` 定义 `DeployParams / UpgradeParams / GatewayStatus / OperationResult` 等 dataclass。
- **FR-7 amis-admin 管理页**: `gateway/admin/__init__.py` + `gateway/admin/instance_admin.py` + `gateway/admin/ops_admin.py`：注册到 `site`，展示实例列表、控制操作按钮、状态刷新。
- **FR-8 HTTP API**: `gateway/api/router.py`：挂载到 `app`，提供 `GET /api/gateway/instances`、`POST /api/gateway/instances`、`POST /api/gateway/instances/{id}/start`、`/stop`、`/restart`、`/status`、`/upgrade`、`/rollback`、`/deploy`。
- **FR-9 日志与审计**: 复用 `core/settings` + Python logging；所有控制操作写入结构化日志，包含 exchange/kind/instance_id/operator/result。

## Non-Functional Requirements
- **NFR-1 Python 版本**: 与 `pyproject.toml` 一致 `>=3.12`。
- **NFR-2 依赖**: 仅使用项目已有依赖（FastAPI / sqlmodel / pydantic-settings 等）；可选 `psutil`（在 `pyproject.toml` 中不强制，代码中以 try/except import 降级为 `os.kill` 方案）。
- **NFR-3 代码风格**: 单文件不超过 500 行，使用 dataclass / pydantic 模型定义输入输出；`ruff` `select = ["E","F","W"]`。
- **NFR-4 可测试**: 所有调用 `subprocess` / `os` / `shutil` 的模块必须可 mock；提供 `tests/gateway/` 目录。
- **NFR-5 可扩展**: 新增交易所只需在 `controllers/` 目录下新增实现并在 registry 注册，无需修改 core / api / admin。

## Constraints
- **Technical**: Master 端在 FastAPI 进程内同步执行网关控制命令；长时操作（部署/升级）采用阻塞调用（超时 300s）。
- **Business**: 回滚必须使用已存在的 backup 目录（升级时自动生成）；不支持"从空目录回滚"。
- **Dependencies**: `gateway_python_dev_guide.md` 为唯一契约来源；配置模板文件名遵循 `生产环境.config.xml.sample.Level2` 风格。

## Assumptions
- Master 运行用户对 `install_dir` 具有读写执行权限。
- 网关二进制、CA 证书文件、XML 模板均由外部运维预先放入 `install_dir` 或随 zip 包提供。
- 监控端口（mdgw 默认 7501，tgw 默认 7500）可在本地 `127.0.0.1:port` 连通；无法连通视为"启动失败"。

## Acceptance Criteria

### AC-1: 抽象层与注册机制
- **Given**: 已安装的 master 代码
- **When**: 导入 `gateway.controllers.registry`
- **Then**: `registry.get("szse", "mdgw")` 返回 `SzseMdgwController`；`registry.get("sse", "mdgw")` 返回子类但方法抛 `NotImplementedError`；`registry.list_all()` 返回所有已注册 `(exchange, kind)` 对。
- **Verification**: `programmatic`

### AC-2: 深交所 mdgw 部署
- **Given**: 空目录 + zip 包（内含 `mdgw` + `cfg/*.config.xml.sample*`）
- **When**: 调用 `SzseMdgwController.deploy(archive_path, gwid="MDGW001", env_id=0)`
- **Then**: `{install_dir}/mdgw/mdgw` 可执行、`cfg/config.xml` 存在、返回 `OperationResult(success=True)`。
- **Verification**: `programmatic`

### AC-3: 网关启停
- **Given**: 已部署的网关目录 + 可执行二进制（测试用 mock 替换真实二进制）
- **When**: 调用 `controller.start()` -> `controller.status()` -> `controller.stop()` -> `controller.status()`
- **Then**: 第一次 status `running=True`，第二次 `running=False`；pid 文件生命周期正确。
- **Verification**: `programmatic`

### AC-4: 升级与回滚
- **Given**: 已部署的 mdgw，有备份目录
- **When**: `upgrade(new_archive)` 失败
- **Then**: 自动回滚到备份（`manifest.json` 存在），最终二进制与配置恢复至升级前。
- **Verification**: `programmatic`

### AC-5: HTTP API 响应
- **Given**: 已注册 API 路由
- **When**: 调用 `POST /api/gateway/instances` 创建实例，`POST /api/gateway/instances/{id}/status`
- **Then**: 返回 `200 OK`，JSON body 含 `running` / `pid` / `monitor_port` / `gateway_dir`。
- **Verification**: `programmatic`

### AC-6: amis-admin 可见
- **Given**: 启动 master
- **When**: 访问 `GET /admin/gateway/*`
- **Then**: 能看到"网关控制"分组及其子页面（实例管理 / 运维操作）。
- **Verification**: `human-judgment`

### AC-7: SSE / BJSE 预留
- **Given**: 运行 registry.list_all()
- **When**: 检查返回列表
- **Then**: 包含 `("sse","mdgw")`、`("sse","tgw")`、`("bjse","mdgw")`、`("bjse","tgw")` 条目。
- **Verification**: `programmatic`

## Open Questions
- [ ] 网关部署的 zip 包解压行为与内部目录结构是否需要更显式的约定（例如 `mdgw_YYYYMMDD_linux.zip` 内部根目录名）？当前实现会处理单层子目录合并。
- [ ] 控制命令（升级/回滚）是否需要二次确认 / 审计写入 DB？当前实现写入日志即可。
- [ ] HTTP API 是否需要鉴权？当前复用 master 现有 auth；若需更细粒度鉴权，可在后续迭代引入 `Depends(auth.requires(roles=...))`。
