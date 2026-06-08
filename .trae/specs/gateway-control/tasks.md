# Master 网关控制 - 实现任务清单

## [ ] Task 1: 搭建网关控制模块骨架（包 + 配置 + 数据模型 + 错误）
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 创建 `master/gateway/__init__.py`、`master/gateway/core/`、`master/gateway/controllers/`、`master/gateway/admin/`、`master/gateway/api/`。
  - 在 `master/core/settings.py` 新增 `gateway_install_root`、`gateway_backup_root` 两个可选配置（默认 `./data/gateways/install` / `./data/gateways/backup`）。
  - 在 `master/gateway/core/errors.py` 定义 `GatewayError` 及子类 `ConfigError`、`BinaryError`、`ProcessError`、`UpgradeError`，含错误码字段。
  - 在 `master/gateway/core/models.py` 定义：`GatewayInstance(pydantic BaseModel)`（id / exchange / kind / name / gateway_dir / version / created_at）、`OperationResult`、`DeployParams`、`UpgradeParams`、`GatewayStatus`。
- **Acceptance Criteria Addressed**: AC-1（部分：为后续实现提供基础）
- **Test Requirements**:
  - `programmatic` 能正常 import `master.gateway.core.errors` 和 `master.gateway.core.models`。
  - `programmatic` pydantic 模型能校验必填字段。
- **Notes**: 保持单文件 <= 500 行。

## [ ] Task 2: 进程管理工具（GatewayProcess）
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - `master/gateway/core/process.py`：`GatewayProcess` 类，封装 start / stop / restart / is_running / get_pid / wait_for_monitor 等基础能力。
  - 使用 `subprocess.Popen(cwd=gateway_dir, start_new_session=True)` 启动；将 PID 写入 `{gateway_dir}/.{binary_name}.pid`。
  - 停止流程：读取 PID 文件，优先 `SIGTERM`，等待 `timeout` 秒后若仍存在则 `SIGKILL`。可选使用 `psutil`（如果已安装），否则回退到 `os.kill` / `os.kill(pid, 0)`。
  - 监控端口就绪：`socket.create_connection(("127.0.0.1", monitor_port), timeout=1)` 轮询直到成功或超时。
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `programmatic` mock `subprocess.Popen` 与 `socket`，验证 start 写入 PID 文件并调用 `wait_for_monitor` 成功。
  - `programmatic` mock 进程存在/不存在场景，验证 stop 流程会调用 `SIGTERM` 并在超时后调用 `SIGKILL`。
- **Notes**: 类设计为纯工具，不负责业务语义（业务语义在上层 Controller）。

## [ ] Task 3: 抽象层与注册中心（GatewayControllerABC + Registry）
- **Priority**: P0
- **Depends On**: Task 1, Task 2
- **Description**:
  - `master/gateway/controllers/base.py`：
    - `GatewayControllerABC` 定义抽象方法：`preflight / deploy / start / stop / restart / upgrade / rollback / status`。
    - `GatewayControllerRegistry`：dict 映射 `(exchange, kind) -> cls`；提供 `register()`、`get()`、`list_all()`；提供 `@registry.register(exchange, kind)` 装饰器。
  - `master/gateway/controllers/__init__.py`：导出并触发各子类注册（import-time）。
- **Acceptance Criteria Addressed**: AC-1, AC-7
- **Test Requirements**:
  - `programmatic` `registry.get("szse", "mdgw")` 正确返回类。
  - `programmatic` `registry.list_all()` 包含所有目标交易所与种类。
  - `programmatic` 调用 SSE/BJSE 占位控制器方法会抛 `NotImplementedError`。
- **Notes**: Registry 为模块级单例。

## [ ] Task 4: 深交所控制器实现（mdgw + tgw）
- **Priority**: P0
- **Depends On**: Task 3
- **Description**:
  - `master/gateway/controllers/szse_mdgw.py`：
    - `deploy(archive_path: Path, params: DeployParams)`：解压 zip 到 `{install_root}/{instance_id}`，合并可能存在的子目录；选择与 `env_id/level/access_mode` 匹配的 XML 模板，替换占位符 `__GWID__` 等生成 `cfg/config.xml`；chmod +x 二进制。
    - `preflight()`：检查二进制、ca.crt、端口占用、磁盘空间。
    - `start/stop/restart/status`：调用 GatewayProcess。
    - `upgrade(new_archive, params: UpgradeParams)`：备份当前二进制+配置到 `{backup_root}/{instance_id}/{timestamp}`，停止、替换二进制、启动、写入 `manifest.json`；失败自动 `rollback`。
    - `rollback(manifest_path)`：从备份目录恢复二进制与配置并重启。
  - `master/gateway/controllers/szse_tgw.py`：在 mdgw 逻辑上增加 `server_list.xml` 支持；`deploy` 额外接收 `server_list_groups`；配置迁移能力（把旧版内嵌 `server_list` 抽取为独立文件）。
  - 引入 `master/gateway/core/config_tools.py`：XML 模板选择、占位符替换、server_list XML 生成、版本字符串解析（从文件名或 `strings` 输出回退）。
- **Acceptance Criteria Addressed**: AC-2, AC-3, AC-4
- **Test Requirements**:
  - `programmatic` deploy：使用临时目录 + mock zip（包含最小二进制与 sample 文件）验证目录结构与 config.xml 内容。
  - `programmatic` upgrade/rollback：mock subprocess/socket，验证调用序列与备份目录。
  - `programmatic` tgw 的 server_list 生成输出合法 XML。
- **Notes**: 避免对真实二进制执行 `./mdgw`，用 mock 代替；单测需在无外部依赖的环境可跑。

## [ ] Task 5: SSE / BJSE 骨架 + 注册
- **Priority**: P1
- **Depends On**: Task 3
- **Description**:
  - 创建 `master/gateway/controllers/sse_mdgw.py`、`sse_tgw.py`、`bjse_mdgw.py`、`bjse_tgw.py`，继承 `GatewayControllerABC`，所有操作方法 `raise NotImplementedError("交易所控制器预留")`。
  - 在 `master/gateway/controllers/__init__.py` 中使用 registry 注册全部四个实现。
- **Acceptance Criteria Addressed**: AC-7
- **Test Requirements**:
  - `programmatic` 调用任意 SSE/BJSE 控制器方法会抛 `NotImplementedError`。
- **Notes**: 类文件保持简短，便于后续增量实现。

## [ ] Task 6: amis-admin 管理界面（实例管理 + 操作页）
- **Priority**: P0
- **Depends On**: Task 4
- **Description**:
  - `master/gateway/admin/__init__.py`：导出 `GatewayAdminApp`。
  - `master/gateway/admin/store.py`：内存实例存储（`List[GatewayInstance]`），提供 CRUD + 持久化到本地 JSON 文件（`{data_root}/gateway_instances.json`）。
  - `master/gateway/admin/instance_admin.py`：`ModelAdmin` 形式的实例列表页（新增 / 删除 / 查看）；`page_schema = PageSchema(label="网关实例", icon="fa fa-server")`。
  - `master/gateway/admin/ops_admin.py`：`PageAdmin` 展示操作面板，支持 start/stop/restart/status/upgrade/rollback，通过 ajax 调用 HTTP API；页面使用 amis 的 Form + 按钮配置。
  - 在 `master/gateway/admin/__init__.py` 组装 `GatewayAdminApp(AdminApp)`，统一挂载到 `site`。
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `human-judgment` 启动 master 后能在 admin 看到"网关控制"分组及子页面。
  - `programmatic` `GatewayAdminApp` 可被 import 且 `register_admin` 能完成注册而不报错。
- **Notes**: 由于 amis-admin 采用 SQLModel ModelAdmin，实例存储在 JSON 文件足以（不新增 DB 表）。

## [ ] Task 7: FastAPI HTTP API 路由
- **Priority**: P0
- **Depends On**: Task 4, Task 5, Task 6
- **Description**:
  - `master/gateway/api/router.py`：创建 `APIRouter(prefix="/api/gateway", tags=["gateway"])`，实现以下端点：
    - `GET /instances` 返回实例列表。
    - `POST /instances` 创建实例。
    - `DELETE /instances/{instance_id}` 删除实例。
    - `GET /instances/{instance_id}` 实例详情。
    - `POST /instances/{instance_id}/deploy` 接受 multipart 上传 archive + JSON 参数，调用控制器 deploy。
    - `POST /instances/{instance_id}/start`、`/stop`、`/restart`、`/status` 调用对应控制器方法。
    - `POST /instances/{instance_id}/upgrade` 接受 archive + 可选 version 参数。
    - `POST /instances/{instance_id}/rollback` 接受 manifest_path 参数。
    - `GET /controllers` 返回已注册控制器列表（exchange / kind / cls）。
  - 统一错误处理：捕获 `GatewayError` 转为 400/500 HTTP 响应。
  - 在 `master/main.py` 导入并 `app.include_router(gateway_router)`；注册 `GatewayAdminApp` 到 `site`。
- **Acceptance Criteria Addressed**: AC-5, AC-7
- **Test Requirements**:
  - `programmatic` 使用 `httpx.AsyncClient` + `TestClient`（或直接 FastAPI TestClient）验证 `/api/gateway/controllers` 返回值包含 `szse`、`sse`、`bjse`。
  - `programmatic` `POST /instances` 成功后可在 `GET /instances` 中查到。
- **Notes**: 文件上传通过 `UploadFile` 保存到临时目录，再传递给控制器。

## [ ] Task 8: 单元测试 & 集成测试
- **Priority**: P0
- **Depends On**: Task 2, 3, 4, 5, 7
- **Description**:
  - `tests/gateway/`：
    - `test_registry.py`：验证 registry 能正确注册/查找 SZSE 控制器，且预留 SSE/BJSE 方法抛 `NotImplementedError`。
    - `test_process.py`：使用 `unittest.mock.patch("subprocess.Popen")` 模拟启动/停止，验证 pid 文件生命周期与信号。
    - `test_szse_mdgw.py`：使用 `tmp_path` 创建最小 zip + sample，验证 deploy 生成 `cfg/config.xml` 且二进制可执行。
    - `test_szse_tgw.py`：验证 server_list.xml 生成。
    - `test_api.py`：使用 `from fastapi.testclient import TestClient` 创建一个仅包含 gateway router 的最小 FastAPI 实例，跑 `/api/gateway/controllers`、`/instances`。
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3, AC-4, AC-5, AC-7
- **Test Requirements**:
  - `programmatic` 在 master 根目录执行 `python -m pytest tests/gateway -q` 全部通过。
- **Notes**: 测试不依赖外部网络/真实网关二进制；尽量 mock 外部调用。

## [ ] Task 9: 集成冒烟测试 + 文档说明
- **Priority**: P1
- **Depends On**: Task 6, Task 7
- **Description**:
  - 在 `master/gateway/__init__.py` 顶部添加 docstring，说明"本模块实现网关控制，首期支持深交所，预留上交所/北交所"。
  - 在 `master/gateway/controllers/__init__.py` 描述如何新增新交易所控制器（创建文件 + `@registry.register(...)` 即可）。
- **Acceptance Criteria Addressed**: AC-6, AC-7
- **Test Requirements**:
  - `human-judgment` 开发者能根据 docstring 在 15 分钟内理解如何新增一个新交易所控制器。
- **Notes**: 不创建额外 README markdown 文件，使用现有 docstring + inline 注释。
