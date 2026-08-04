# 修复 Master 项目登录页面调用 Spec

## Why
Master 项目的 admin 页面无法成功调用 fastapi-user-auth 库提供的登录界面。根本原因是 `MyAuthAdminSite` 继承了 `AdminSite`（来自 fastapi_amis_admin）而非 `AuthAdminSite`（来自 fastapi_user_auth），导致包含登录页面的 `UserAuthApp` 从未被注册，权限校验未启用，认证中间件未挂载。此外，登录页面渲染所需的 `vue.js` 静态资源缺失，会导致即使路由存在页面也无法渲染。

## What Changes
- 将 `MyAuthAdminSite` 的基类从 `AdminSite` 改为 `AuthAdminSite`，使 `UserAuthApp`（含登录、注册、用户管理等）自动注册
- 通过构造函数正确传递 `auth` 对象给 `AuthAdminSite`，而非在 `globals.py` 中创建后手动赋值
- 在 `main.py` 中挂载认证中间件（`AuthenticationMiddleware`），使 `request.user` 可用
- 补充缺失的 `vue/dist/vue.js` 和 `vue/dist/vue.min.js` 静态资源文件，使 `page.html` / `app.html` 模板能正常加载

## Impact
- Affected specs: 无（本次为 Bug 修复）
- Affected code:
  - [master/core/auth.py](file:///Users/shun/PythonProject/sretools/master/core/auth.py) — 修改 `MyAuthAdminSite` 基类
  - [master/core/globals.py](file:///Users/shun/PythonProject/sretools/master/core/globals.py) — 调整 `site` 和 `auth` 的创建方式
  - [master/main.py](file:///Users/shun/PythonProject/sretools/master/main.py) — 挂载认证中间件
  - [master/static/](file:///Users/shun/PythonProject/sretools/master/static) — 新增 `vue/dist/` 静态资源

## ADDED Requirements

### Requirement: 登录页面注册与路由
系统 SHALL 通过继承 `AuthAdminSite` 自动注册 `UserAuthApp`，从而提供 `/admin/auth/login` 登录页面路由。

#### Scenario: 未登录用户访问 admin 页面
- **WHEN** 未登录用户访问 `/admin` 下任何需要权限的页面
- **THEN** 系统 307 重定向到 `/admin/auth/login?redirect=<原始路径>`

#### Scenario: 已登录用户访问登录页
- **WHEN** 已登录用户访问 `/admin/auth/login`
- **THEN** 系统 307 重定向到首页（`redirect` 参数或 `/`）

### Requirement: 认证中间件挂载
系统 SHALL 在 FastAPI 应用上挂载 `AuthenticationMiddleware`，使用 `auth.backend` 作为认证后端，使每个请求的 `request.user` 和 `request.auth` 可用。

#### Scenario: 请求携带有效 token
- **WHEN** 请求的 Cookie 或 Header 中携带有效的 `Authorization: bearer <token>`
- **THEN** `request.user` 为对应的 `User` 对象

#### Scenario: 请求未携带 token
- **WHEN** 请求未携带 Authorization
- **THEN** `request.user` 为 `None`，请求继续处理（由页面权限决定是否重定向）

### Requirement: Vue.js 静态资源可用
系统 SHALL 在 `/static/vue/dist/` 下提供 `vue.js` 和 `vue.min.js`，使 admin 页面和登录页的 AMIS 渲染不因 vue 加载 404 而白屏。

#### Scenario: 浏览器加载 admin 页面
- **WHEN** 浏览器请求 `/static/vue/dist/vue.min.js`
- **THEN** 返回 200 和 vue.js 脚本内容

## MODIFIED Requirements

### Requirement: MyAuthAdminSite 初始化
`MyAuthAdminSite` SHALL 继承 `AuthAdminSite`，并通过构造函数接收 `auth` 参数，在初始化时完成 `UserAuthApp` 的注册。

修改前：
```python
class MyAuthAdminSite(AdminSite):
    pass
```

修改后：
```python
class MyAuthAdminSite(AuthAdminSite):
    pass
```

#### Scenario: site 创建后登录页可用
- **WHEN** `MyAuthAdminSite(settings, engine=async_db, auth=auth)` 创建完成
- **THEN** `UserAuthApp` 已注册，`/admin/auth/login` 路由在 `mount_app` 后可访问

### Requirement: globals.py 中 auth 与 site 的创建
`globals.py` SHALL 将 `auth` 对象通过构造函数传递给 `MyAuthAdminSite`，避免在 site 创建后再手动赋值 `site.auth = auth`。

修改前：
```python
auth = Auth(db=async_db, token_store=DbTokenStore(...))
site = MyAuthAdminSite(settings, engine=async_db)
auth = Auth(db=async_db, token_store=DbTokenStore(...))  # 重复创建
site.auth = auth
```

修改后：
```python
auth = Auth(db=async_db, token_store=DbTokenStore(...))
site = MyAuthAdminSite(settings, engine=async_db, auth=auth)
```

#### Scenario: auth 与 site 正确关联
- **WHEN** 应用启动
- **THEN** `site.auth` 与全局 `auth` 为同一对象，`UserAuthApp` 内的 `auth` 也为同一对象
