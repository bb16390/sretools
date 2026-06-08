# Master 网关控制 - 验证清单

- [ ] Checkpoint 1: 代码结构与包可导入
  - [ ] 目录 `master/gateway/`、`core/`、`controllers/`、`admin/`、`api/` 存在且有 `__init__.py`
  - [ ] 能在 Python 中 `import master.gateway` 不报错

- [ ] Checkpoint 2: 数据模型与错误类
  - [ ] `GatewayInstance` pydantic 模型能实例化并校验字段
  - [ ] `GatewayError` 子类均能被 raise/catch，且携带 `code/message/details`

- [ ] Checkpoint 3: 进程管理 (GatewayProcess)
  - [ ] start 时写入 PID 文件并启动 subprocess（cwd=gateway_dir）
  - [ ] stop 发送 SIGTERM，超时后发送 SIGKILL，并清理 PID 文件
  - [ ] is_running 基于 PID 文件存在性 + 进程存活判断
  - [ ] wait_for_monitor 轮询本地监控端口直到超时

- [ ] Checkpoint 4: 抽象层与 Registry
  - [ ] `GatewayControllerABC` 定义 preflight/deploy/start/stop/restart/upgrade/rollback/status 抽象方法
  - [ ] `GatewayControllerRegistry.register` / `get` / `list_all` 工作正常
  - [ ] 启动时 registry 至少包含 ("szse","mdgw")、("szse","tgw")、("sse","mdgw")、("sse","tgw")、("bjse","mdgw")、("bjse","tgw")

- [ ] Checkpoint 5: 深交所 mdgw / tgw 实现
  - [ ] deploy 能解压 zip、合并子目录、选择模板、生成 `cfg/config.xml` 并设置 +x
  - [ ] tgw deploy 支持生成独立的 `server_list.xml`
  - [ ] upgrade 会停止、备份、替换二进制、启动，失败时自动回滚
  - [ ] rollback 从 manifest.json 恢复二进制与配置并重启
  - [ ] status 返回 running / pid / monitor_port / gateway_dir / version

- [ ] Checkpoint 6: SSE / BJSE 占位
  - [ ] 四个占位控制器均继承自 `GatewayControllerABC`
  - [ ] 调用任意操作方法时抛出 `NotImplementedError`

- [ ] Checkpoint 7: amis-admin 集成
  - [ ] `GatewayAdminApp` 能 register 到 `site` 而不报错
  - [ ] 启动 master 后在后台看到"网关控制"分组及子页面

- [ ] Checkpoint 8: FastAPI HTTP API
  - [ ] `/api/gateway/controllers` 返回含 szse / sse / bjse 的控制器列表
  - [ ] `/api/gateway/instances` CRUD 接口响应正常
  - [ ] 捕获 `GatewayError` 并转为结构化 JSON 错误响应（code/message/details）

- [ ] Checkpoint 9: 测试可执行
  - [ ] `pytest tests/gateway -q` 在干净环境中通过，无网络或外部二进制依赖
  - [ ] 关键流程（deploy / start-stop / upgrade-rollback / api）有覆盖

- [ ] Checkpoint 10: 扩展路径清晰
  - [ ] 模块 docstring 描述了如何新增新交易所控制器（新增文件 + @registry.register）
  - [ ] 新增控制器无需修改 core / api / admin
