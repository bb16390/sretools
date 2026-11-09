# SRE Tools Web（Vue 3 管理台）

替代 `master/libs/fastapi_amis_admin` 页面层的独立前端。当前与 amis 后台（`/admin`）**并行运行**，接口全部复用现有 FastAPI 路由，未修改后端行为。

## 技术选型

| 能力 | 选型 |
| --- | --- |
| 框架 | Vue 3 + Vite + TypeScript |
| 路由 | Vue Router 4（history 模式） |
| 状态 | Pinia（登录态、用户信息） |
| 请求 | Axios（Bearer Token + 统一响应拆包） |
| UI | Element Plus |

## 目录结构

```
web/
├── index.html
├── package.json
├── vite.config.ts          # 开发代理 /admin /api /static -> 127.0.0.1:5500
├── tsconfig.json
└── src/
    ├── api/
    │   ├── http.ts         # Axios 实例、token、401 处理、BaseApiOut 拆包
    │   ├── auth.ts         # 登录/用户信息/登出
    │   ├── crud.ts         # ModelAdmin 通用 list/item CRUD
    │   └── types.ts
    ├── components/
    │   └── CrudPage.vue    # 通用列表 + 筛选 + 分页 + 新建/编辑/删除
    ├── config/
    │   └── resources.ts    # 页面、数据源、任务、用户等资源定义
    ├── layouts/
    │   └── AdminLayout.vue
    ├── router/index.ts
    ├── stores/auth.ts
    ├── views/
    │   ├── HomeView.vue
    │   ├── LoginView.vue
    │   ├── FileUploadView.vue
    │   └── NotFoundView.vue
    └── main.ts
```

## 开发

后端（默认 `0.0.0.0:5500`）：

```bash
cd /Users/shun/PythonProject/sretools
.venv/bin/python -m uvicorn master.main:app --host 127.0.0.1 --port 5500
```

前端：

```bash
cd web
npm install
npm run dev        # http://127.0.0.1:5173
```

Vite 会把 `/admin`、`/api`、`/static` 代理到 `VITE_PROXY_TARGET`（默认 `http://127.0.0.1:5500`），因此不需要后端改 CORS。

其它脚本：

```bash
npm run typecheck  # vue-tsc 类型检查
npm run build      # 类型检查 + 生产构建，产物在 web/dist
npm run preview    # 本地预览构建产物
```

## 认证方式（已实测）

| 用途 | 方法与路径 | 说明 |
| --- | --- | --- |
| 登录 | `POST /admin/auth/form/login/api` | JSON `{username,password}`，返回 `data.access_token` |
| 登录（OAuth2） | `POST /admin/auth/gettoken` | `application/x-www-form-urlencoded`，备用 |
| 当前用户 | `GET /admin/auth/userinfo` | `Authorization: Bearer <token>` |
| 登出 | `GET /admin/auth/logout` | 返回 307 跳转，不是 JSON；前端忽略响应并清理本地 token |

- Token 保存在 `localStorage['sretools.token']`，请求头使用 `Bearer`。
- 响应统一为 `{status, msg, data, code}`：
  - `status === 0` 表示成功；
  - **HTTP 200 + `status === 401`** 表示已登录但缺少页面/操作权限，前端只提示、不退出登录；
  - **HTTP 401** 表示未登录或 token 失效，前端清理登录态并跳转 `/login`。
- 本地 `root/root` 拥有权限（Casbin 根账号规则）；`admin/admin` 目前缺少 `page:list` 等策略，会在页面上看到权限提示。

## 页面与后端接口映射

| 前端路由 | 资源 | 后端 apiBase |
| --- | --- | --- |
| `/pages` | 页面管理 | `/admin/NavPageAdmin` |
| `/collector/datasources` | 数据源 | `/admin/collector/DataSourceAdmin` |
| `/collector/tasks` | 采集任务 | `/admin/collector/CollectorTaskAdmin` |
| `/system/users` | 用户 | `/admin/auth/UserAdmin` |
| `/system/roles` | 角色 | `/admin/auth/RoleAdmin` |
| `/system/login-history` | 登录记录（只读） | `/admin/auth/LoginHistoryAdmin` |
| `/system/casbin-rules` | 权限规则（只读，可刷新策略） | `/admin/auth/CasbinRuleAdmin` |
| `/tools/file-upload` | 文件上传 | `POST /api/file-upload/submit`（multipart） |

CRUD 约定：

- 列表：`POST {base}/list?page=1&perPage=10&showTotal=true&orderBy=id&orderDir=desc`，请求体为过滤条件；
- 详情：`GET {base}/item/{id}`；
- 新建：`POST {base}/item`（页面管理的 `parent_id` 走 query 参数）；
- 更新：`PUT {base}/item/{id}`；
- 删除：`DELETE {base}/item/{id}`，支持逗号分隔多个 id。
- 文本模糊过滤使用 `[~]关键词` 前缀（如 `{"name":"[~]任务"}`）。

新增页面时，只需在 `src/config/resources.ts` 增加一个 `CrudResource` 并在 `router/index.ts` 注册路由，无需新增组件。

## 生产构建与 FastAPI 托管方案

构建：

```bash
cd web
VITE_BASE=/web/ npm run build   # 产物 web/dist
```

`VITE_BASE` 决定 Vue Router 的 base 与静态资源前缀。推荐挂载到 `/web`，不占用 amis 的 `/admin`。

在 `master/main.py` 中（**本次未修改**，确认后再加）于 amis 的 `site.mount_app(app)` 之后添加：

```python
from pathlib import Path

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent


class SPAStaticFiles(StaticFiles):
    """history 模式下，未命中的路径回退到 index.html。"""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response


app.mount("/web", SPAStaticFiles(directory=BASE_DIR / "web" / "dist", html=True), name="web")
```

要点：

- `/admin` 的 amis 挂载保持不变，新前端只新增 `/web`；
- 若想直接放在根路径 `/`，`VITE_BASE=/` 构建，并把 `app.mount` 改为 `/`，同时要处理与现有 `/`、`/api`、`/mcp` 路由的优先级；
- 也可用 Nginx 托管 `web/dist` 并反向代理 `/admin`、`/api`，前后端分域名时设置 `VITE_API_BASE`。

## 已知缺口与后续事项

1. **Gateway 管理页不可用**：`master/apps/gateway` 下的 `GatewayAdminApp` 未在 `main.py` 注册（gateway 路由被注释），因此没有可迁移页面。
2. **MCP Server 无管理页面**：仅挂载 `/mcp`，本次未覆盖。
3. **采集任务新建已修复**：模型为 `job_id` 增加 `uuid4` 默认值，为 `worker_id`、`last_run_time`、`transform_script` 增加空字符串默认值，规避 `NOT NULL` 约束；实测新建成功。
4. **暂停/恢复参数已兼容**：`CollectorTaskAdmin.control` 同时接受 `action` 与 `actio`，并把 `pause→stop`、`resume→start` 归一化；非法值返回 422，路由路径与旧 amis 调用保持不变。
5. **预览接口已修复**：`preview` 优先读取 `conf["src_datasource"]`，回退历史字段 `src_database`，返回数据源的 `id/node/name/url`；缺失或非法 ID 返回 422。
6. **数据源选项接口缺失**：旧 amis 配置引用 `DataSourceAdmin/datasource_options`，后端实际只注册了 `database_options`，旧页面该下拉可能取不到数据。
7. **页面管理不支持名称搜索**：`NavPageAdmin.list_filter` 未包含 `label`，前端只能按可见/激活/锁定/自定义/分组/上级 ID 过滤；名称搜索需后端补 filter 配置。
8. **上传接口不落盘**：`/api/file-upload/submit` 目前只回显文件名、类型、大小等元数据，不保存文件（与旧后台行为一致）。
9. **Element Plus 全量引入**：构建产物约 1.17MB（gzip 约 389KB），后续可改用按需引入/自动导入优化。

## 待你拍板

1. 是否最终下线 amis（当前保留，建议迁移完成并回归后再评估）。
2. 是否需要为 Gateway / MCP 补管理页面。

> `admin` 账号的权限策略已在应用启动时自动补齐：所有页面 `page:list`；ModelAdmin 页面额外补 `page:read/create/update/delete` 与 `page`；首页、文件上传、APIDocs 补 `page`（用于 amis 菜单展示与页面访问）。幂等，不会重复写入。
