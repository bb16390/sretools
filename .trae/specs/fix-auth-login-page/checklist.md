# Checklist

- [x] `master/core/auth.py` 中 `MyAuthAdminSite` 继承 `AuthAdminSite` 而非 `AdminSite`
- [x] `master/core/auth.py` 中模板路径覆盖逻辑（`App.__default_template_path__` / `Page.__default_template_path__`）保留不变
- [x] `master/core/globals.py` 中 `auth` 对象只创建一次，无重复创建
- [x] `master/core/globals.py` 中 `auth` 通过构造函数传递给 `MyAuthAdminSite`，而非手动赋值 `site.auth = auth`
- [x] `master/main.py` 中在 `site.mount_app(app)` 之后调用了 `auth.backend.attach_middleware(app)`
- [x] `master/static/vue/dist/vue.js` 文件存在且可访问
- [x] `master/static/vue/dist/vue.min.js` 文件存在且可访问
- [x] 启动应用后访问 `/admin` 未登录时重定向到 `/admin/auth/form/login`
- [x] 登录页面 `/admin/auth/form/login` 正常渲染，无 vue.js 404 白屏
- [x] 使用 admin/admin 登录成功后可访问 admin 管理页面
