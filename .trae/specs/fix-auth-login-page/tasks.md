# Tasks

- [x] Task 1: 修改 `MyAuthAdminSite` 基类为 `AuthAdminSite`
  - [x] SubTask 1.1: 在 `master/core/auth.py` 中将 `from fastapi_amis_admin.admin import AdminSite` 替换为 `from fastapi_user_auth.admin import AuthAdminSite`
  - [x] SubTask 1.2: 将 `class MyAuthAdminSite(AdminSite)` 改为 `class MyAuthAdminSite(AuthAdminSite)`
  - [x] SubTask 1.3: 保留已有的模板路径覆盖逻辑（`App.__default_template_path__` / `Page.__default_template_path__`）

- [x] Task 2: 调整 `globals.py` 中 auth 与 site 的创建方式
  - [x] SubTask 2.1: 移除重复的 `auth = Auth(...)` 第二次创建（第 23 行）
  - [x] SubTask 2.2: 将 `site = MyAuthAdminSite(settings, engine=async_db)` 改为 `site = MyAuthAdminSite(settings, engine=async_db, auth=auth)`
  - [x] SubTask 2.3: 移除 `site.auth = auth` 手动赋值（已通过构造函数传递）

- [x] Task 3: 在 `main.py` 中挂载认证中间件
  - [x] SubTask 3.1: 在 `site.mount_app(app)` 之后添加 `auth.backend.attach_middleware(app)`

- [x] Task 4: 补充缺失的 `vue/dist/vue.js` 静态资源
  - [x] SubTask 4.1: 下载 Vue 2.7.x 的 `vue.js` 和 `vue.min.js` 到 `master/static/vue/dist/` 目录

- [x] Task 5: 验证登录页面可访问
  - [x] SubTask 5.1: 启动应用，访问 `/admin` 确认未登录时重定向到 `/admin/auth/form/login`
  - [x] SubTask 5.2: 确认登录页面正常渲染（vue.js 加载成功，无白屏）
  - [x] SubTask 5.3: 使用 admin/admin 登录确认登录流程正常

# Task Dependencies
- Task 2 依赖 Task 1（需要 `MyAuthAdminSite` 接受 `auth` 参数才能正确传递）
- Task 3 依赖 Task 2（需要 globals.py 中 auth 正确创建）
- Task 5 依赖 Task 1, 2, 3, 4（全部修改完成后才能验证）
- Task 4 可与 Task 1, 2, 3 并行执行
